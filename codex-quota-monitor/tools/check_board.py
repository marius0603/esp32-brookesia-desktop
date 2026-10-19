"""Check a connected board's identity and actual acceptance of a real quota frame."""
import argparse
import json
from pathlib import Path
import sys
import time
import serial

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quota_monitor.model import encode_frame, normalize
from quota_monitor.rpc import CodexClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    client = CodexClient()
    try:
        packet = normalize(client.read_quota())
        packet.update(stale_after=180, warning=20, critical=10)
    finally:
        client.close()
    connection = serial.Serial(port=None, baudrate=115200, timeout=0.3, write_timeout=2)
    connection.dtr = False
    connection.rts = False
    connection.port = args.port
    result = {"port": args.port, "checked_at": int(time.time()), "identity": False, "quota_ack": False}
    with connection:
        deadline, next_send = time.monotonic() + 18, 0
        buffer = bytearray()
        while time.monotonic() < deadline:
            buffer.extend(connection.read(min(connection.in_waiting or 1, 512)))
            if len(buffer) > 4096:
                buffer.clear()
            while b"\n" in buffer:
                line, _, rest = buffer.partition(b"\n")
                buffer = bytearray(rest)
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                if not isinstance(message, dict):
                    continue
                if message.get("type") == "hello" and message.get("device") == "codex-quota-monitor" and message.get("v") == 1:
                    result["identity"] = True
                if result["identity"] and message.get("type") == "ack" and message.get("sampled_at") == packet["sampled_at"] and message.get("windows") == len(packet["windows"]):
                    result["quota_ack"] = True
                    result["sampled_at"] = packet["sampled_at"]
                    result["remaining"] = [100 - window["used"] for window in packet["windows"]]
                    for field in ("firmware", "volume", "audio_ready", "pmu_ready", "uptime_ms"):
                        result[field] = message.get(field)
                    (ROOT / "runtime/board-check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
                    print(json.dumps(result, indent=2))
                    return
            if result["identity"] and time.monotonic() >= next_send:
                connection.write(encode_frame(packet))
                next_send = time.monotonic() + 2
    print(json.dumps(result, indent=2))
    raise SystemExit("Device did not confirm quota reception; inspect startup and USB logs.")


if __name__ == "__main__":
    main()
