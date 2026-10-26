"""Install Chinese story titles and register the OFL supplement; reboot afterwards."""
import argparse
import contextlib
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

from deploy_audiobook_sleep import StoryClient

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--port', required=True)
args = parser.parse_args()
package = ROOT.parent / 'packages/apps/local.audiobook.debug.0.2.2.bpk'
with zipfile.ZipFile(package) as archive:
    assert archive.testzip() is None
    manifest = json.loads(archive.read('manifest.json'))
    assert manifest['package']['id'] == 'local.audiobook' and manifest['package']['version'] == '0.2.2'
    assert 'fonts/index.json' not in json.loads(archive.read('res/root.json'))['assets']
    supplement = archive.read('res/fonts/story-title-extra.ttf')

stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
folder = ROOT / 'runtime' / ('audiobook-titles-' + stamp)
folder.mkdir(parents=True)
backup = '/sdcard/resource-backups/audiobook-titles-' + stamp
index_path = '/littlefs/system/fonts/index.json'
font_path = '/littlefs/system/fonts/audiobook-title-extra.ttf'
report = {'backup': backup, 'restart_required': True, 'package_sha256': hashlib.sha256(package.read_bytes()).hexdigest()}

with StoryClient(args.port, timeout=30) as client:
    client.hello()
    def call(service, function, params=None):
        return client.call(service, function, params or {})['result']

    report['tracks_before'] = call('Audiobook', 'List')['tracks']
    report['playback_before'] = call('Audiobook', 'GetState')
    original = call('Storage', 'FSReadText', {'Path': index_path})
    (folder / 'fonts-before.json').write_text(original, encoding='utf-8')
    index = json.loads(original)
    assert any(f['id'] == 'zh_CN' for f in index['fonts']), 'System Chinese fallback is missing'
    call('Storage', 'FSCopyTree', {'From': index_path, 'To': backup + '/fonts-index.json', 'Overwrite': False})
    if call('Storage', 'FSStat', {'Path': font_path})['exists']:
        call('Storage', 'FSCopyTree', {'From': font_path, 'To': backup + '/title-extra.ttf', 'Overwrite': False})
    app = next(a for a in call('SystemCore', 'ListApps') if a['manifest']['id'] == 'local.audiobook')
    call('SystemCore', 'StopApp', {'AppId': app['app_id']})
    with (folder / 'install.log').open('w', encoding='utf-8') as log:
        with contextlib.redirect_stderr(log):
            result = client.transfer('install_bpk', package, None, False)
    assert result['ok'], result
    call('Storage', 'FSCopyTree', {'From': '/littlefs/apps/local.audiobook/res/fonts/story-title-extra.ttf',
        'To': font_path, 'Overwrite': True})
    assert call('Storage', 'FSStat', {'Path': font_path})['size'] == len(supplement)
    # App documents cannot register fontSet assets. Add one global alias while
    # retaining every other registration exactly, including the Chinese fallback.
    others = [f for f in index['fonts'] if f['id'] != 'audiobook_title']
    index['fonts'] = others + [{'id': 'audiobook_title', 'kind': 'file', 'src': 'audiobook-title-extra.ttf',
        'languages': ['en', 'zh_CN'], 'fallbacks': ['${font.zh_CN}']}]
    text = json.dumps(index, ensure_ascii=False, indent=2) + '\n'
    staging = '/littlefs/usb/audiobook-fonts-index.json'
    call('Storage', 'FSWriteText', {'Path': staging, 'Data': text})
    assert json.loads(call('Storage', 'FSReadText', {'Path': staging})) == index
    call('Storage', 'FSRename', {'From': staging, 'To': index_path})
    assert json.loads(call('Storage', 'FSReadText', {'Path': index_path})) == index
    report['tracks_after'] = call('Audiobook', 'List')['tracks']
    assert report['tracks_after'] == report['tracks_before']
    report.update(complete=True, font_sha256=hashlib.sha256(supplement).hexdigest())
    (folder / 'deployment.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Installed audiobook 0.2.2; original fonts and SD stories preserved. Restart once to load the title supplement.')
