"""Use the pinned Brookesia USB protocol without toggling ESP reset lines."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quota_monitor.brookesia import StableUsbClient
sys.stdout.reconfigure(encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--service')
    parser.add_argument('--function')
    parser.add_argument('--args', default='{}')
    parser.add_argument('--install', type=Path)
    args = parser.parse_args()
    with StableUsbClient(args.port, timeout=args.timeout) as client:
        hello = client.hello()
        if args.install:
            result = client.transfer('install_bpk', args.install, None, False)
        elif args.service:
            if not args.function:
                parser.error('--service requires --function')
            result = client.call(args.service, args.function, json.loads(args.args))
        else:
            result = {'hello': hello, 'status': client.status()}
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
