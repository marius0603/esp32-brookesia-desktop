"""Apply the verified 0.2.5 -> 0.2.6 weather UI delta on a nearly-full device."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import time
import zipfile

from deploy_wallpaper_shift import WallpaperClient

ROOT = Path(__file__).resolve().parents[1]
FILES = ('res/screens/main.json', 'manifest.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--bpk', type=Path, default=ROOT.parent/'packages/apps/local.weather.debug.0.2.6.bpk')
    parser.add_argument('--previous', type=Path, default=ROOT.parent/'packages/apps/local.weather.debug.0.2.5.bpk')
    args = parser.parse_args()
    with zipfile.ZipFile(args.bpk) as new, zipfile.ZipFile(args.previous) as old:
        assert new.testzip() is None and old.testzip() is None
        assert set(new.namelist()) == set(old.namelist())
        assert all(new.read(n) == old.read(n) for n in new.namelist() if n not in FILES)
        manifest = json.loads(new.read('manifest.json'))
        assert manifest['package']['id'] == 'local.weather' and manifest['package']['version'] == '0.2.6'
        folder = ROOT/'runtime'/('weather-clouds-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
        folder.mkdir(parents=True)
        for n in FILES:
            (folder/Path(n).name).write_bytes(new.read(n))
    with WallpaperClient(args.port, timeout=25) as c:
        c.hello()
        def storage(name, params):
            return c.call('Storage', name, params)['result']
        current = json.loads(storage('FSReadText', {'Path': '/littlefs/apps/local.weather/manifest.json'}))
        assert current['package']['version'] in ('0.2.5', '0.2.6')
        apps = c.call('SystemCore', 'ListApps', {})['result']
        app = next(a for a in apps if a['manifest']['id'] == 'local.weather')
        if app['state'] == 'Running':
            c.call('SystemCore', 'StopApp', {'AppId': app['app_id']})
            time.sleep(1)
        backup = '/sdcard/resource-backups/'+folder.name
        storage('FSMkdir', {'Path': backup})
        for n in FILES:
            target = '/littlefs/apps/local.weather/'+n
            storage('FSCopyTree', {'From': target, 'To': backup+'/'+Path(n).name, 'Overwrite': True})
            result = c.transfer('put', folder/Path(n).name, 'weather-update.bin', True)
            assert result['ok'], result
            storage('FSRename', {'From': '/littlefs/usb/weather-update.bin', 'To': target})
            assert storage('FSStat', {'Path': target})['size'] == (folder/Path(n).name).stat().st_size
        assert json.loads(storage('FSReadText', {'Path': '/littlefs/apps/local.weather/manifest.json'})) == manifest
        print('Weather cloud resources updated; restart the device to rediscover version 0.2.6.')


if __name__ == '__main__':
    main()
