"""Install the audiobook layout, retaining stories, bookmark and speaker volume."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time
import zipfile

from deploy_audiobook_sleep import StoryClient

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    version = json.loads((ROOT.parent / 'versions.json').read_text(encoding='utf-8'))['apps']['local.audiobook']
    package = ROOT.parent / 'packages/apps' / ('local.audiobook.debug.' + version + '.bpk')
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        metadata = json.loads(archive.read('manifest.json'))['package']
        assert metadata['id'] == 'local.audiobook' and metadata['version'] == version
        assert archive.read('res/images/launcher_icon.png') == (ROOT.parent / 'themes/cartoon-q-v1/flash-fallback/audiobook.png').read_bytes()
    output = ROOT / 'runtime/audiobook-layout-deployment.json'
    report = {'passed': False, 'version': version, 'package_sha256': hashlib.sha256(package.read_bytes()).hexdigest(),
              'backup': '/sdcard/resource-backups/audiobook-layout-' + datetime.now().strftime('%Y%m%d-%H%M%S')}

    def call(client, service, function, params=None):
        return client.call(service, function, params or {})['result']

    with StoryClient(args.port, timeout=30) as client:
        client.hello()
        before = report['playback_before'] = call(client, 'Audiobook', 'GetState')
        assert not before['sleep_active'], 'Preserve the running sleep timer; install after it ends or is cancelled'
        assert not call(client, 'DeviceModes', 'GetState')['screen_locked'], 'Unlock with double volume+ first'
        call(client, 'DeviceModes', 'Wake')
        report['tracks_before'] = call(client, 'Audiobook', 'List')['tracks']
        report['volume_before'] = call(client, 'AudioPlayback', 'GetVolume')
        bookmark_path = '/littlefs/audiobook-bookmark.json'
        bookmark_exists = call(client, 'Storage', 'FSStat', {'Path': bookmark_path})['exists']
        app = next(a for a in call(client, 'SystemCore', 'ListApps') if a['manifest']['id'] == 'local.audiobook')
        call(client, 'Storage', 'FSCopyTree', {'From': '/littlefs/apps/local.audiobook',
                                             'To': report['backup'], 'Overwrite': False})
        # Keep the installed native launcher cache while adding new app images.
        image_path = '/littlefs/apps/local.audiobook/res/images/index.json'
        installed_images = json.loads(call(client, 'Storage', 'FSReadText', {'Path': image_path}))
        launcher = next(i for i in installed_images['images'] if i['id'] == 'launcher_icon')
        preserved_package = ROOT / 'runtime' / ('audiobook-preserved-' + version + '.bpk')
        with zipfile.ZipFile(package) as source, zipfile.ZipFile(preserved_package, 'w', zipfile.ZIP_DEFLATED) as target:
            for name in source.namelist():
                data = source.read(name)
                if name == 'res/images/index.json':
                    images = json.loads(data)
                    images['images'] = [launcher if i['id'] == 'launcher_icon' else i for i in images['images']]
                    data = (json.dumps(images, ensure_ascii=False, separators=(',', ':'))+'\n').encode()
                target.writestr(name, data)
        package = preserved_package
        if app['state'] in ('Running', 'Paused', 'Starting'):
            call(client, 'SystemCore', 'StopApp', {'AppId': app['app_id']})
        bookmark = call(client, 'Storage', 'FSReadText', {'Path': bookmark_path}) if bookmark_exists else None
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for attempt in range(3):
        try:
            with StoryClient(args.port, timeout=30) as client:
                client.hello()
                assert client.transfer('install_bpk', package, None, False)['ok']
            break
        except RuntimeError as exc:
            if attempt == 2 or 'Wait timeout after 5000 ms' not in str(exc):
                raise
            print('Waiting for asynchronous app cleanup before reconnecting.', flush=True)
            time.sleep(7)
    with StoryClient(args.port, timeout=30) as client:
        client.hello()
        app = next(a for a in call(client, 'SystemCore', 'ListApps') if a['manifest']['id'] == 'local.audiobook')
        assert app['manifest']['version'] == version
        installed_images = json.loads(call(client, 'Storage', 'FSReadText', {'Path': image_path}))
        assert next(i for i in installed_images['images'] if i['id'] == 'launcher_icon') == launcher
        call(client, 'SystemCore', 'StartApp', {'AppId': app['app_id']})
        if before['active'] and before['path'] and before['path'] != '@tone':
            try:
                call(client, 'AudioPlayback', 'SetVolume', {'Volume': 0})
                call(client, 'Audiobook', 'Play', {'Path': before['path'], 'Position': before['position']})
                deadline = time.monotonic() + 15
                while True:
                    state = call(client, 'Audiobook', 'GetState')
                    if state['error']:
                        raise RuntimeError(state['error'])
                    if state['state'] == 'Playing' and state['bytes_written']:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Restored story did not decode')
                    time.sleep(.2)
                if before['state'] == 'Paused':
                    call(client, 'Audiobook', 'Pause')
                    call(client, 'Audiobook', 'Seek', {'Seconds': before['position']})
            finally:
                call(client, 'AudioPlayback', 'SetVolume', {'Volume': report['volume_before']})
        time.sleep(1.2)
        active = call(client, 'SystemCore', 'GetActiveApp')
        assert active['app_id'] == app['app_id'] and active['state'] == 'Running' and not active['last_error'], active
        assert call(client, 'Audiobook', 'List')['tracks'] == report['tracks_before']
        assert call(client, 'AudioPlayback', 'GetVolume') == report['volume_before']
        if bookmark is not None:
            assert call(client, 'Storage', 'FSReadText', {'Path': bookmark_path}) == bookmark
        report.update(passed=True, active=active, bookmark_preserved=bookmark is not None,
                      volume_preserved=True, story_count=len(report['tracks_before']))
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Audiobook ' + version + ' running; stories, bookmark and volume preserved.')


if __name__ == '__main__':
    main()
