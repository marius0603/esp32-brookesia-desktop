"""Measure actual LVGL whole-screen redraws separately from USB/app latency."""
import argparse
import json
from pathlib import Path
import time
from verify_child_mode import Client

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--label', default='current')
    args = parser.parse_args()
    report = {'label': args.label, 'samples': [], 'passed': False}
    with Client(args.port, timeout=25) as c:
        c.hello()
        def call(s, f, p=None):
            return c.call(s, f, p or {})['result']
        def desktop():
            active = call('SystemCore', 'GetActiveApp')
            if active.get('manifest', {}).get('id') not in (None, 'brookesia.system.super.shell'):
                call('SystemCore', 'RequestCloseApp', {'AppId': active['app_id']})
            time.sleep(1)
        try:
            call('DeviceModes', 'Wake')
            desktop()
            report['initial_memory'] = call('Utils', 'GetMemorySnapshot')
            apps = call('SystemCore', 'ListApps')
            for target in (None, 'local.flipclock', 'local.weather', 'local.codex.quota'):
                if target:
                    app = next(a for a in apps if a['manifest']['id'] == target)
                    call('SystemCore', 'RequestCloseApp', {'AppId': app['app_id']})
                    time.sleep(.7)
                    call('SystemCore', 'StartApp', {'AppId': app['app_id']})
                    time.sleep(2)
                    desktop()
                samples = [call('DeviceModes', 'ProfileRefresh', {'Force': True}) for _ in range(3)]
                assert all(0 < s['forced_refresh_us'] < 5000000 and s['last_strips'] > 0 for s in samples), samples
                report['samples'].append({'returned_from': target or 'desktop', 'redraws': samples})
                print((target or 'desktop')+': full redraw ms '+str([round(s['forced_refresh_us']/1000, 1) for s in samples]), flush=True)
            report['final_memory'] = call('Utils', 'GetMemorySnapshot')
            report['passed'] = True
        finally:
            try:
                desktop()
            finally:
                output = ROOT/'runtime'/('display-profile-'+args.label+'.json')
                output.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
