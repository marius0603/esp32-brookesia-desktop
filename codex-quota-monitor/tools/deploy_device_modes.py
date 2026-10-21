"""Deploy weather and Settings assets, backing up each existing file to SD.

Use after an app-only firmware update; never writes NVS or parent credentials.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from verify_child_mode import Client


def main():
    repo = Path(sys.argv[1]).resolve()
    weather = repo / 'brookesia-apps/weather/build'
    files = [(weather / name, '/littlefs/apps/local.weather/' + name) for name in (
        'app/main.js', 'res/screens/main.json', 'res/root.json', 'manifest.json',
        'res/profile.json', 'res/images/index.json', 'res/images/launcher_icon.png')]
    for screen in ('display','sound'):
        files.append((repo / f'platform/super_s3_216/overrides/settings-{screen}.json',
                      f'/littlefs/apps/brookesia.general.settings/res/screens/{screen}.json'))
    report = {'backup': '/sdcard/resource-backups/device-modes-' + datetime.now().strftime('%Y%m%d-%H%M%S'), 'files': []}
    with Client('COM5', timeout=30) as c:
        c.hello()
        def call(s, f, p=None): return c.call(s, f, p or {})['result']
        active = call('SystemCore', 'GetActiveApp')
        if active and active.get('manifest', {}).get('id') != 'brookesia.system.super.shell':
            app_id = active.get('app_id')
            apps = call('SystemCore', 'ListApps')
            app = next(a for a in apps if a['app_id'] == app_id)
            if app['manifest']['id'] != 'brookesia.system.super.shell':
                call('SystemCore', 'RequestCloseApp', {'AppId': app_id})
                time.sleep(.8)
        call('Storage', 'FSMkdir', {'Path': report['backup']})
        for index, (source, target) in enumerate(files):
            assert source.is_file()
            before = call('Storage', 'FSStat', {'Path': target})
            backup = report['backup'] + '/' + str(index) + '-' + source.name
            if before['exists']:
                call('Storage', 'FSCopyTree', {'From': target, 'To': backup, 'Overwrite': True})
                assert call('Storage', 'FSStat', {'Path': backup})['size'] == before['size']
            c.transfer('put', source, 'device-update.bin', True)
            call('Storage', 'FSRename', {'From': '/littlefs/usb/device-update.bin', 'To': target})
            assert call('Storage', 'FSStat', {'Path': target})['size'] == source.stat().st_size
            report['files'].append({'target': target, 'bytes': source.stat().st_size,
                                    'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
            print('Updated ' + target, flush=True)
    (ROOT / 'runtime/device-modes-deployment.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
