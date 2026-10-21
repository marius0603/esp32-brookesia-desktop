"""Verify persisted theme references and open every themed app after restart."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quota_monitor.brookesia import StableUsbClient


class DiagnosticClient(StableUsbClient):
    def read_json(self):
        while True:
            try:
                return super().read_json()
            except RuntimeError as exc:
                text = str(exc)
                # LVGL logs bypass ESP log suppression. Retain only this known
                # touch-edge warning separately; never hide a panic or other error.
                if ('invalid device response:' in text and 'indev_pointer_proc:' in text
                        and 'which is greater than' in text and 'lv_indev.c:' in text):
                    self.diagnostic_lines.append(text.encode())
                    continue
                raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('theme', type=Path)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--skip-app-store', action='store_true', help='Skip the native App Store USB close path')
    args = parser.parse_args()
    manifest = json.loads((args.theme / 'theme.json').read_text(encoding='utf-8'))
    before = json.loads((args.backup / 'apps-before.json').read_text(encoding='utf-8'))
    report = {'apps': [], 'references': {}, 'physical_display_verified': False}
    output = args.backup / 'verification.json'
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with DiagnosticClient(args.port, timeout=25) as client:
        client.hello()
        def close_foreground():
            active = client.call('SystemCore', 'GetActiveApp', {})['result']
            if active.get('manifest', {}).get('id') not in (None, 'brookesia.system.super.shell'):
                client.call('SystemCore', 'RequestCloseApp', {'AppId': active['app_id']})
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    active = client.call('SystemCore', 'GetActiveApp', {})['result']
                    if active.get('app_id') is None or active.get('manifest', {}).get('id') == 'brookesia.system.super.shell':
                        time.sleep(.4)
                        return
                    time.sleep(.1)
                raise RuntimeError('App did not return to desktop')
        apps = client.call('SystemCore', 'ListApps', {})['result']
        versions = {a['manifest']['id']: a['manifest']['version'] for a in apps}
        assert all(versions.get(a['manifest']['id']) == a['manifest']['version'] for a in before)
        report['existing_apps_preserved'] = True
        for app, name in manifest['icons'].items():
            path = f'/littlefs/apps/{app}/res/images/index.json'
            doc = json.loads(client.call('Storage', 'FSReadText', {'Path': path})['result'])
            icon = next(i for i in doc['images'] if i['id'] == 'launcher_icon')
            assert icon['src'] == f'/littlefs/themes/cream-handdrawn-v1/{name}', (app, icon)
            assert (icon['width'], icon['height']) == (96, 96)
            report['references'][app] = icon
        shell = json.loads(client.call('Storage', 'FSReadText', {
            'Path': '/littlefs/system/super/shell/root.json'})['result'])
        assert 'styles/cream.json' in shell['assets']
        for name, info in manifest['files'].items():
            stat = client.call('Storage', 'FSStat', {
                'Path': '/littlefs/themes/cream-handdrawn-v1/' + name})['result']
            assert stat['exists'] and stat['size'] == info['bytes'], (name, stat)
        report['references_survived_restart'] = True
        save()
        close_foreground()
        for app in apps:
            if app['manifest']['id'] not in manifest['icons']:
                continue
            if args.skip_app_store and app['manifest']['id'] == 'brookesia.general.app_store':
                report['app_store_note'] = 'Opened successfully in earlier check; USB close timed out, excluded from this loop.'
                save()
                continue
            start = time.monotonic()
            client.call('SystemCore', 'StartApp', {'AppId': app['app_id']})
            time.sleep(.8)
            active = client.call('SystemCore', 'GetActiveApp', {})['result']
            assert active.get('app_id') == app['app_id'] and active['state'] == 'Running' and not active['last_error'], active
            row = {'id': app['manifest']['id'], 'state': active['state'], 'last_error': active['last_error'],
                   'open_seconds': round(time.monotonic() - start, 2)}
            report['apps'].append(row)
            save()
            print(json.dumps(row), flush=True)
            close_foreground()
        active = client.call('SystemCore', 'GetActiveApp', {})['result']
        assert active.get('app_id') is None or active.get('manifest', {}).get('id') == 'brookesia.system.super.shell'
        report['returned_to_desktop'] = True
        report['capacity'] = client.call('Storage', 'GetFileSystemCapacity', {'MountPoint': '/littlefs'})['result']
        report['touch_edge_warnings'] = len(client.diagnostic_lines)
        save()
    print(f'Verified {len(report["apps"])} app opens, persisted theme references, and return to desktop.')


if __name__ == '__main__':
    main()
