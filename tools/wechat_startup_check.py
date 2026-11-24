"""Check the bound WeChat channel without sending or claiming a new delivery."""
import argparse
from collections import deque
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import subprocess
import time

from wechat_brief import DEFAULT_CONFIG, find_response

PROXY = ("127.0.0.1", 7890)
WECHAT_HOST = "ilinkai.weixin.qq.com"
STATUSES = {"sent", "rejected", "uncertain"}


def utc_string(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds")


def last_delivery(path):
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as stream:
        lines = deque(stream, maxlen=100)
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("stage") == "send_finished" and event.get("status") in STATUSES:
            return {"status": event["status"], "at": event.get("at")}
    return {}


def latest_inbound(account, status):
    value = status.get("lastInboundAt")
    if isinstance(value, (int, float)) and value > 0:
        return utc_string(value / 1000)
    # The plugin updates this cache when the bound account receives context.
    # Read only the timestamp so account and conversation data stay private.
    if account and Path(account).name == account:
        cache = Path.home() / ".openclaw/openclaw-weixin/accounts" / (account + ".context-tokens.json")
        if cache.is_file():
            return utc_string(cache.stat().st_mtime)
    return None


def get_channel(config):
    env = os.environ.copy()
    env["PATH"] = str(Path(config["node"]).parent) + os.pathsep + env.get("PATH", "")
    for attempt in range(2):
        try:
            result = subprocess.run(
                [config["node"], config["cli"], "channels", "status", "--probe", "--json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env=env, timeout=28, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            response = find_response(result.stdout, lambda value: "channelAccounts" in value)
            if result.returncode == 0 and response:
                accounts = response["channelAccounts"].get("openclaw-weixin", [])
                channel = next((row for row in accounts if row.get("accountId") == config["account"]), {})
                if channel.get("running") or attempt == 1:
                    return channel
        except subprocess.TimeoutExpired:
            pass
        if attempt == 0:
            time.sleep(2)
    return None


def wechat_endpoint():
    # One credential-free HTTPS request through the same proxy as OpenClaw.
    connection = http.client.HTTPSConnection(*PROXY, timeout=6)
    try:
        connection.set_tunnel(WECHAT_HOST, 443)
        connection.request("HEAD", "/", headers={"Host": WECHAT_HOST})
        return 200 <= connection.getresponse().status < 500
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def check(config_path, launch):
    report = {"checked_at": utc_string(time.time()), "codex_launch": launch}
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if config.get("channel") != "openclaw-weixin":
        raise ValueError("Expected the bound WeChat channel")
    channel = get_channel(config)
    report["gateway_reachable"] = channel is not None
    report["channel_running"] = bool(channel and channel.get("running") and channel.get("configured")
                                     and not channel.get("lastError"))
    report["wechat_endpoint_reachable"] = wechat_endpoint()
    report["last_inbound_at"] = latest_inbound(config["account"], channel or {})
    report["last_delivery"] = last_delivery(config_path.parent / "brief-attempts.jsonl")
    delivery = report["last_delivery"].get("status")
    if not report["gateway_reachable"]:
        result, message = "gateway_unavailable", "OpenClaw 网关未就绪。"
    elif not report["channel_running"]:
        result, message = "channel_unavailable", "微信通道未启动或报告异常。"
    elif not report["wechat_endpoint_reachable"]:
        result, message = "wechat_endpoint_unreachable", "当前代理无法连接微信服务。"
    elif delivery in {"rejected", "uncertain"}:
        result, message = "delivery_unconfirmed", "微信通道在线，最近一次简报未取得发送回执。"
    elif not report["last_inbound_at"] or delivery != "sent":
        result, message = "history_missing", "微信通道在线，暂缺实际收信或发送回执记录。"
    else:
        result, message = "ready", "微信通道在线，已核对最近的真实收发记录。"
    return dict(report, result=result), message


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--codex-launch")
    args = parser.parse_args()
    if args.codex_launch and not args.codex_launch.replace(":", "").isdigit():
        parser.error("Invalid desktop launch identity")
    try:
        report, message = check(args.config, args.codex_launch)
        output = args.config.parent / "codex-wechat-status.json"
        temp = output.with_name(f"{output.name}.{os.getpid()}.tmp")
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(output)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        print("微信启动检查无法读取本机通道配置或结果。")
        return 2
    print(message)
    return int(report["result"] != "ready")


if __name__ == "__main__":
    raise SystemExit(main())
