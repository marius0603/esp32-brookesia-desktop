"""Check repeated app transitions with the native RGB565 wallpaper active."""
import argparse
import json
from pathlib import Path
import time

from verify_child_mode import Client

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM5')
    args = parser.parse_args()
    report = {'passed': False, 'transitions': []}
    with Client(args.port, timeout=25) as c:
        c.hello()
        def call(service, name, params=None):
            return c.call(service, name, params or {})['result']
        def wait(predicate, seconds=15):
            deadline = time.monotonic()+seconds
            while time.monotonic() < deadline:
                value = predicate()
                if value:
                    return value
                time.sleep(.1)
            raise AssertionError('App transition did not finish')
        def wallpaper():
            try:
                layers = call('DeviceModes', 'GetWeatherLayers')['layers']
            except RuntimeError as error:
                # A full redraw can hold LVGL longer than this diagnostic's
                # 100 ms lock timeout. The outer wait remains bounded to 15 s.
                if str(error) == 'call_failed: GUI busy':
                    return None
                raise
            node = next((n for n in layers if n['kind'] == 'wallpaper'), None)
            if not node:
                return None
            assert node['pixel_format'] == 0x12 and node['source_width'] == node['source_height'] == 486, node
            assert node['scale_x'] == node['scale_y'] == 256, node
            assert -6 <= node['x'] <= 0 and -6 <= node['y'] <= 0, node
            assert not any(n.get('kind') == 'surface' and n.get('width', 0) >= 400 and
                           n.get('height', 0) >= 400 and n.get('effective_opacity') == 255 and
                           n.get('background_opacity') == 255 for n in layers[layers.index(node)+1:]), layers
            return node
        def close_active():
            active = call('SystemCore', 'GetActiveApp')
            if active.get('manifest', {}).get('id') not in (None, 'brookesia.system.super.shell'):
                call('SystemCore', 'RequestCloseApp', {'AppId': active['app_id']})
            return wait(wallpaper)
        try:
            call('DeviceModes', 'Wake')
            close_active()
            report['initial_memory'] = call('Utils', 'GetMemorySnapshot')
            apps = call('SystemCore', 'ListApps')
            for name in ('local.flipclock', 'local.weather', 'local.codex.quota')*2:
                app = next(a for a in apps if a['manifest']['id'] == name)
                call('SystemCore', 'RequestCloseApp', {'AppId': app['app_id']})
                time.sleep(.6)
                started = time.monotonic()
                call('SystemCore', 'StartApp', {'AppId': app['app_id']})
                active = wait(lambda: (a if (a := call('SystemCore', 'GetActiveApp')).get('app_id') == app['app_id'] and a.get('state') == 'Running' else None))
                assert not active['last_error'], active
                opened = time.monotonic()-started
                time.sleep(1)
                started = time.monotonic()
                frame = close_active()
                report['transitions'].append({'app': name, 'open_control_seconds': opened,
                                               'close_control_seconds': time.monotonic()-started, 'wallpaper': frame})
                print(name+': open/return succeeded; native size and unscaled RGB565 verified', flush=True)
            report['final_memory'] = call('Utils', 'GetMemorySnapshot')
            report['passed'] = True
        finally:
            try:
                close_active()
            finally:
                (ROOT/'runtime/wallpaper-switch-verification.json').write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
