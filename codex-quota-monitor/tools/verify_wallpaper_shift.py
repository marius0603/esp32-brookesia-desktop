"""Verify actual wallpaper movement, app pause, screen-off pause and wake resume."""
import argparse
import json
from pathlib import Path
import time

from verify_child_mode import Client

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--quick', action='store_true', help='Only check a real timed move after a rendering-only update')
    args = parser.parse_args()
    report = {'passed': False, 'scope': 'timed_render' if args.quick else 'full', 'samples': []}
    with Client(args.port, timeout=25) as client:
        client.hello()
        def call(service, name, params=None):
            return client.call(service, name, params or {})['result']
        def frame(phase):
            layers = call('DeviceModes', 'GetWeatherLayers')['layers']
            node = next((n for n in layers if n['kind'] == 'wallpaper'), None)
            if node is None and phase.startswith('app_'):
                # Shell switches its bottom screen flow while an app is open.
                report['samples'].append({'phase': phase, 'at': time.monotonic(), 'frame': None})
                return None
            assert node is not None, layers
            if phase in ('initial', 'desktop', 'wake', 'wake_delay', 'wake_resume'):
                above = layers[layers.index(node)+1:]
                assert not any(n.get('kind') == 'surface' and n.get('width', 0) >= 400 and
                               n.get('height', 0) >= 400 and n.get('effective_opacity') == 255 and
                               n.get('background_opacity') == 255 for n in above), above
            assert node['width'] == node['height'] == 486, node
            assert -6 <= node['x'] <= 0 and -6 <= node['y'] <= 0, node
            assert node['x']+node['width'] >= 480 and node['y']+node['height'] >= 480, node
            assert node['effective_opacity'] == 255, node
            assert node['pixel_format'] == 0x12 and node['source_width'] == node['source_height'] == 486, node
            assert node['scale_x'] == node['scale_y'] == 256, node
            report['samples'].append({'phase': phase, 'at': time.monotonic(), 'frame': node})
            return node['x'], node['y']
        def unchanged(position, seconds, phase):
            deadline = time.monotonic()+seconds
            while time.monotonic() < deadline:
                assert frame(phase) == position, report['samples'][-1]
                time.sleep(min(2, max(0, deadline-time.monotonic())))
        def changed(position, phase, timeout=75):
            started = time.monotonic()
            while time.monotonic()-started < timeout:
                current = frame(phase)
                if current != position:
                    return current, time.monotonic()-started
                time.sleep(2)
            raise AssertionError(f'Wallpaper did not move within {timeout} seconds')
        def close_active():
            active = call('SystemCore', 'GetActiveApp')
            if active.get('manifest', {}).get('id') not in (None, 'brookesia.system.super.shell'):
                call('SystemCore', 'RequestCloseApp', {'AppId': active['app_id']})
                time.sleep(1)
        app = None
        try:
            call('DeviceModes', 'Wake')
            close_active()
            initial = frame('initial')
            moved, elapsed = changed(initial, 'desktop')
            report['first_move_wait_seconds'] = elapsed
            print('Desktop wallpaper moved within its minute interval; all edges covered', flush=True)
            if args.quick:
                report['passed'] = True
                return
            apps = call('SystemCore', 'ListApps')
            app = next(a for a in apps if a['manifest']['id'] == 'local.flipclock')
            call('SystemCore', 'RequestCloseApp', {'AppId': app['app_id']})
            time.sleep(.8)
            call('SystemCore', 'StartApp', {'AppId': app['app_id']})
            time.sleep(3)
            active = call('SystemCore', 'GetActiveApp')
            assert active.get('app_id') == app['app_id'] and active['state'] == 'Running', active
            position = frame('app_start')
            unchanged(position, 65, 'app_pause')
            print('Wallpaper held throughout 65 seconds with a foreground app', flush=True)
            close_active()
            call('DeviceModes', 'SleepNow')
            time.sleep(1)
            assert call('DeviceModes', 'GetState')['screen_asleep']
            position = frame('sleep_start')
            unchanged(position, 65, 'screen_off_pause')
            print('Wallpaper held throughout 65 seconds with screen off', flush=True)
            call('DeviceModes', 'Wake')
            time.sleep(1)
            assert not call('DeviceModes', 'GetState')['screen_asleep']
            position = frame('wake')
            unchanged(position, 45, 'wake_delay')
            _, elapsed = changed(position, 'wake_resume', timeout=30)
            report['resume_wait_after_45_seconds'] = elapsed
            report['passed'] = True
            print('Wallpaper resumed after a fresh minute following wake', flush=True)
        finally:
            call('DeviceModes', 'Wake')
            close_active()
            filename = 'wallpaper-shift-quick-verification.json' if args.quick else 'wallpaper-shift-verification.json'
            (ROOT/'runtime'/filename).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
