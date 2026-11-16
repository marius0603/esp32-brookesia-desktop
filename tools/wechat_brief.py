"""Send one explicitly prepared work brief through the locally bound WeChat channel."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT.parent / 'private/openclaw-binding/brief-config.json'


def delivery_sent(data):
    return data.get('payload', {}).get('deliveryStatus') == 'sent'


def send(config_path, body, event_id, dry_run=False):
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
    # Persist before sending. Timeout/crash can mean delivery is uncertain;
    # never automatically resend an uncertain message under the same event id.
    events[key] = 'uncertain'
    record.write_text(json.dumps(events, indent=2) + '\n', encoding='utf-8')
    env = os.environ.copy()
    env['PATH'] = str(Path(config['node']).parent) + os.pathsep + env.get('PATH', '')
    result = subprocess.run([
        config['node'], config['cli'], 'message', 'send', '--channel', config['channel'],
        '--account', config['account'], '--target', config['target'],
        '--message', body, '--json',
    ], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=55, env=env)
    # The CLI has no top-level ok field on success. Check actual platform delivery.
    raw = result.stdout.strip()
    try:
        data, _ = json.JSONDecoder().raw_decode(raw[raw.index('{'):])
    except (ValueError, json.JSONDecodeError):
        return {'status': 'uncertain', 'reason': 'invalid_response'}
    status = 'sent' if result.returncode == 0 and delivery_sent(data) else 'failed'
    events[key] = status
    record.write_text(json.dumps(events, indent=2) + '\n', encoding='utf-8')
    # Never echo provider responses, account identifiers, URLs or credentials.
    return {'status': status}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--body-file', type=Path, required=True)
    parser.add_argument('--id', required=True, help='Unique completed-work id, normally the pushed Git SHA')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        result = send(args.config, args.body_file.read_text(encoding='utf-8-sig'), args.id, args.dry_run)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result = {'status': 'not_confirmed', 'reason': type(error).__name__}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] in ('sent', 'dry_run') or (result['status'] == 'already_recorded' and result['previous'] == 'sent') else 1


if __name__ == '__main__':
    sys.exit(main())
