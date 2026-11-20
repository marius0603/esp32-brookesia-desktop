"""Install the square desktop palettes and unified Controls resources over USB."""

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time

from maintenance_client import SharedPowerDiagnosticClient

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'packages/resources/square-control-themes'
FONT = ROOT / 'platform/super_s3_216/littlefs/system/fonts/desktop-theme-extra.ttf'
SHELL = '/littlefs/system/super/shell'
CONTROLS = '/littlefs/apps/brookesia.general.settings/res'
FONT_INDEX = '/littlefs/system/fonts/index.json'
IMAGE_INDEX = SHELL + '/images/index.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM5')
    args = parser.parse_args()
    stamp = 'square-control-themes-' + str(time.time_ns())
    stage = '/sdcard/themes/' + stamp
    with tempfile.TemporaryDirectory() as temp, SharedPowerDiagnosticClient(args.port, timeout=40) as client:
        client.hello()

        def call(service, method, **params):
            return client.call_timeout(service, method, params, 12000).get('result', {})

        def storage(method, **params):
            return call('Storage', method, **params)

        current = call('DeviceModes', 'GetState')
        if current['firmware_version'] != '0.8.3-s3.84' or current['screen_locked']:
            raise SystemExit('Start s3.84 and unlock the screen before installing these resources')
        local = Path(temp)
        originals = []
        files = {}

        def read_json(path):
            return json.loads(storage('FSReadText', Path=path))

        def modified(name, doc):
            path = local / name
            path.write_bytes((json.dumps(doc, ensure_ascii=False, separators=(',', ':')) + '\n').encode())
            return path

        assets = json.loads((ASSETS / 'shell/images/square-images.json').read_bytes())['images']
        image_index = read_json(IMAGE_INDEX)
        image_index['images'] = [item for item in image_index['images']
                                 if not item['id'].startswith('square.')] + assets
        for name in sorted({item['src'] for item in assets}):
            files[SHELL + '/images/' + name] = ASSETS / 'shell/images' / name
        fonts = read_json(FONT_INDEX)
        if not any(entry['id'] == 'desktop_theme' for entry in fonts['fonts']):
            fonts['fonts'].append({'id': 'desktop_theme', 'kind': 'file', 'src': FONT.name,
                                   'languages': ['en', 'zh_CN'], 'fallbacks': ['${font.zh_CN}']})
            files[FONT_INDEX] = modified('font-index.json', fonts)
        files['/littlefs/system/fonts/' + FONT.name] = FONT
        files[IMAGE_INDEX] = modified('image-index.json', image_index)
        for source in ('shell/screens/app_launcher.json', 'shell/templates/launcher_app_button.json',
                       'control/screens/settings_home.json', 'control/screens/display.json',
                       'control/i18n/en.json', 'control/i18n/zh_CN.json'):
            group, relative = source.split('/', 1)
            files[(SHELL if group == 'shell' else CONTROLS) + '/' + relative] = ASSETS / source

        capacity = storage('GetFileSystemCapacity', MountPoint='/littlefs')
        needed = sum(path.stat().st_size for path in files.values())
        if capacity['free_bytes'] < needed:
            raise SystemExit(f'Not enough LittleFS space to update desktop resources ({needed} bytes needed)')
        for index, (target, path) in enumerate(files.items()):
            staged = f'{index}-{path.name}'
            response = client.transfer('put', path, f'sd-themes/{stamp}/{staged}', False)
            assert response['ok'] and response['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
            original = ''
            if storage('FSStat', Path=target)['exists']:
                original = f'{stage}/original-{index}'
                storage('FSCopyTree', From=target, To=original, Overwrite=False)
            originals.append((target, path, f'{stage}/{staged}', original))

        written = []
        try:
            for target, path, staged, original in originals:
                written.append((target, original))
                storage('FSCopyTree', From=staged, To=target, Overwrite=True)
                assert storage('FSStat', Path=target)['size'] == path.stat().st_size, target
                if path.suffix == '.json':
                    assert read_json(target) == json.loads(path.read_bytes()), target
        except Exception:
            for target, original in reversed(written):
                if original:
                    storage('FSCopyTree', From=original, To=target, Overwrite=True)
                else:
                    storage('FSRemove', Path=target)
            raise
        if current['desktop_theme_index'] < 2:
            call('DeviceModes', 'SetDesktopTheme', Index=2)
            time.sleep(3)
        print(f'Installed and verified {len(files)} desktop resources; previous files saved under {stage}.')


if __name__ == '__main__':
    main()
