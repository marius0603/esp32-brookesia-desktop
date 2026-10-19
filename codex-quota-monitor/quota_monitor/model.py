"""Credential-free versioned protocol shared with the ESP32 firmware."""
import math
import time

PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 2048


def normalize(result, sampled_at=None):
    buckets = result.get("rateLimitsByLimitId")
    if isinstance(buckets, dict) and buckets:
        bucket = buckets.get("codex") or next(iter(buckets.values()))
    else:
        bucket = result.get("rateLimits")
    if not isinstance(bucket, dict):
        raise ValueError("quota_unavailable")
    windows = []
    for kind in ("primary", "secondary"):
        raw = bucket.get(kind)
        if not isinstance(raw, dict):
            continue
        used = raw.get("usedPercent")
        minutes = raw.get("windowDurationMins")
        reset = raw.get("resetsAt")
        # Unknown values must never turn into a zero allowance or a full allowance.
        if not isinstance(used, (int, float)) or isinstance(used, bool) or not math.isfinite(used):
            continue
        if not 0 <= used <= 100:
            continue
        if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes <= 0:
            continue
        if reset is not None and (not isinstance(reset, int) or isinstance(reset, bool) or reset <= 0):
            reset = None
        windows.append({"kind": kind, "minutes": minutes, "used": used, "reset_at": reset})
    if not windows:
        raise ValueError("quota_unavailable")
    plan = bucket.get("planType")
    limit_id = bucket.get("limitId")
    return {
        "type": "quota", "v": PROTOCOL_VERSION,
        "sampled_at": int(time.time() if sampled_at is None else sampled_at),
        "status": "ok", "plan": plan if isinstance(plan, str) else "",
        "bucket": limit_id if isinstance(limit_id, str) else "codex", "windows": windows,
    }


def encode_frame(snapshot, now=None):
    import json
    packet = {**snapshot, "sent_at": int(time.time() if now is None else now)}
    data = (json.dumps(packet, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")
    if len(data) > MAX_FRAME_BYTES:
        raise ValueError("frame_too_large")
    return data


def display_status(snapshot, now=None):
    now = time.time() if now is None else now
    sampled = snapshot.get("sampled_at")
    if sampled is not None and now - sampled > snapshot.get("stale_after", 180):
        return "stale"
    return snapshot.get("status", "starting")


def window_name(minutes):
    if minutes == 10080:
        return "每周额度"
    if minutes % 1440 == 0:
        return f"{minutes // 1440} 天额度"
    if minutes % 60 == 0:
        return f"{minutes // 60} 小时额度"
    return f"{minutes} 分钟额度"


def countdown(reset_at, now=None):
    if reset_at is None:
        return "暂无重置时间"
    seconds = int(reset_at - (time.time() if now is None else now))
    if seconds <= 0:
        return "等待同步"
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{days}天 {hours:02d}:{minutes:02d}:{seconds:02d}" if days else f"{hours:02d}:{minutes:02d}:{seconds:02d}"
