"""Send one explicitly prepared work brief through the locally bound WeChat channel."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT.parent / 'private/openclaw-binding/brief-config.json'


def find_response(raw, valid):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='replace')
    raw = raw or ''
    for i, char in enumerate(raw):
        if char != '{':
            continue
        try:
            value, _ = json.JSONDecoder().raw_decode(raw[i:])
        except ValueError:
            continue
        if isinstance(value, dict) and valid(value):
            return value
    return None


def wechat_prepare_rejected(raw):
    return bool(re.search(
        r"\bsendMessage\s+ret\s*=\s*-2\b[^\r\n]{0,120}\berrmsg\s*=\s*prepare failed\b",
        raw or "", re.IGNORECASE,
    ))


def send(config_path, body, event_id, dry_run=False, timeout_seconds=180):
    if not 30 <= timeout_seconds <= 300:
        raise ValueError('Send timeout must be 30 to 300 seconds')
    config_path = config_path.resolve()
    if config_path.is_relative_to(ROOT):
        raise ValueError('Notification config must be outside the repository')
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    if config['channel'] != 'openclaw-weixin':
        raise ValueError('Expected the bound WeChat channel')
    if not body.strip() or len(body.encode('utf-8')) > 3500:
        raise ValueError('Brief must contain 1 to 3500 UTF-8 bytes')
    record = config_path.parent / 'brief-deliveries.json'
    events = json.loads(record.read_text(encoding='utf-8')) if record.exists() else {}
    key = hashlib.sha256(event_id.encode('utf-8')).hexdigest()
    if key in events:
        return {'status': 'already_recorded', 'previous': events[key]}
    if dry_run:
        return {'status': 'dry_run', 'bytes': len(body.encode('utf-8'))}
    env = os.environ.copy()
    env['PATH'] = str(Path(config['node']).parent) + os.pathsep + env.get('PATH', '')
    timings = {}
    def audit(stage, **fields):
        # Metadata only: no text, recipient, account, token or provider output.
        with (config_path.parent / 'brief-attempts.jsonl').open('a', encoding='utf-8') as output:
            output.write(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(), event=key,
                                         stage=stage, **fields)) + '\n')
    def run(args, timeout):
        return subprocess.run([config['node'], config['cli'], *args], capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=timeout, env=env)
    started = time.monotonic()
    try:
        health = run(['gateway', 'health', '--json', '--timeout', '10000'], 30)
        healthy = health.returncode == 0 and find_response(health.stdout, lambda d: d.get('ok') is True)
    except (OSError, subprocess.SubprocessError) as error:
        audit('health', status='not_sent', error=type(error).__name__)
        return {'status': 'not_sent', 'reason': 'gateway_unavailable'}
    timings['health_seconds'] = round(time.monotonic() - started, 2)
    audit('health', status='ready' if healthy else 'not_sent', **timings)
    if not healthy:
        return {'status': 'not_sent', 'reason': 'gateway_unavailable', **timings}

    # A stable key reaches the running Gateway's own inflight/delivery dedupe.
    request_id = 'work-brief-' + hashlib.sha256(
        json.dumps([event_id, body, config['channel'], config['account'], config['target']],
                   ensure_ascii=False).encode('utf-8')).hexdigest()
    params = dict(channel=config['channel'], accountId=config['account'], to=config['target'],
                  message=body, idempotencyKey=request_id)
    def receipt(d):
        return d.get('runId') == request_id and d.get('channel') == config['channel'] and isinstance(d.get('messageId'), str) and bool(d['messageId'])
    events[key] = 'uncertain'
    record.write_text(json.dumps(events, indent=2) + '\n', encoding='utf-8')
    audit('send_started')
    send_started = time.monotonic()
    reason = None
    rejected = False
    try:
        result = run(['gateway', 'call', 'send', '--params', json.dumps(params, ensure_ascii=False),
                      '--timeout', str(min(120000, (timeout_seconds - 10) * 1000)), '--json'], timeout_seconds)
        acknowledged = result.returncode == 0 and find_response(result.stdout, receipt)
        rejected = result.returncode != 0 and (
            wechat_prepare_rejected(result.stderr) or wechat_prepare_rejected(result.stdout)
        )
        if not acknowledged:
            reason = 'wechat_prepare_rejected' if rejected else 'missing_gateway_delivery_receipt'
    except subprocess.TimeoutExpired as error:
        # An acknowledgement already received remains proof even if CLI exit stalls.
        acknowledged = find_response(error.stdout, receipt)
        reason = None if acknowledged else 'gateway_send_timeout'
    except OSError:
        acknowledged = False
        reason = 'sender_process_error'
    status = 'sent' if acknowledged else 'rejected' if rejected else 'uncertain'
    timings['send_seconds'] = round(time.monotonic() - send_started, 2)
    events[key] = status
    record.write_text(json.dumps(events, indent=2) + '\n', encoding='utf-8')
    audit('send_finished', status=status, reason=reason, **timings)
    return {'status': status, **({'reason': reason} if reason else {}), **timings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--body-file', type=Path, required=True)
    parser.add_argument('--id', required=True, help='Unique completed-work id, normally the pushed Git SHA')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--timeout-seconds', type=int, default=180)
    args = parser.parse_args()
    try:
        result = send(args.config, args.body_file.read_text(encoding='utf-8-sig'), args.id, args.dry_run, args.timeout_seconds)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result = {'status': 'not_confirmed', 'reason': type(error).__name__}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] in ('sent', 'dry_run') or (result['status'] == 'already_recorded' and result['previous'] == 'sent') else 1


if __name__ == '__main__':
    sys.exit(main())
