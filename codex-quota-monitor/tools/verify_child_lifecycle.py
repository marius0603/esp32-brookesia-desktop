"""Short lifecycle/memory check of three local apps; never closes the shell."""
import argparse
import json
from pathlib import Path
import time

from verify_child_mode import Client

TARGETS = ('local.childmode', 'local.flipclock', 'local.audiobook')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--cycles', type=int, default=3)
    args = parser.parse_args()
    assert 1 <= args.cycles <= 10
    report = {'cycles': []}
    with Client(args.port, timeout=25) as client:
        client.hello()

        def call(service, function, params=None):
            return client.call(service, function, params or {})['result']

        apps = call('SystemCore', 'ListApps')
        ids = {app['manifest']['id']: app['app_id'] for app in apps}
        active = call('SystemCore', 'GetActiveApp')
        if active.get('manifest', {}).get('id') not in (None, 'brookesia.system.super.shell'):
            raise RuntimeError('Return to the desktop before running this diagnostic')
        for cycle in range(args.cycles):
            for package in TARGETS:
                call('SystemCore', 'StartApp', {'AppId': ids[package]})
                time.sleep(1)
                active = call('SystemCore', 'GetActiveApp')
                assert active.get('manifest', {}).get('id') == package, active
                # Only the explicitly tested app can be closed, never the shell.
                call('SystemCore', 'RequestCloseApp', {'AppId': ids[package]})
                for _ in range(30):
                    time.sleep(.1)
                    active = call('SystemCore', 'GetActiveApp')
                    if active.get('app_id') != ids[package]:
                        break
                else:
                    raise RuntimeError('App close timed out: ' + package)
                time.sleep(.3)
            report['cycles'].append(call('Utils', 'GetMemorySnapshot'))
        report['sd'] = call('SdResources', 'GetState')
        output = Path(__file__).resolve().parents[1] / 'runtime/child-mode-short-lifecycle.json'
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'opens': len(TARGETS) * args.cycles,
                      'memory': [{'internal_free': v['internal']['free_size'],
                                  'external_free': v['external']['free_size']}
                                 for v in report['cycles']]}, indent=2))


if __name__ == '__main__':
    main()
