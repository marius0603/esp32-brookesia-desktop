"""Install square desktop and native app UI resources over USB."""

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time

from maintenance_client import SharedPowerDiagnosticClient
from deploy_clock_widgets import tree_hash

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'packages/resources/square-control-themes'
APP_UI = ROOT / 'packages/resources/square-apps-ui'
CONTROL_UI = ROOT / 'packages/resources/square-controls-center'
STORE_UI = ROOT / 'packages/resources/square-app-store'
FILES_APP = '/littlefs/apps/brookesia.general.files/res'
STORE_APP = '/littlefs/apps/brookesia.general.app_store/res'
FONT = ROOT / 'platform/super_s3_216/littlefs/system/fonts/desktop-theme-extra.ttf'
SHELL = '/littlefs/system/super/shell'
CONTROLS = '/littlefs/apps/brookesia.general.settings/res'
FONT_INDEX = '/littlefs/system/fonts/index.json'
IMAGE_INDEX = SHELL + '/images/index.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM5')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apps-ui-only', action='store_true', help='Stage enlarged desktop and Files resources only')
    mode.add_argument('--controls-ui-only', action='store_true', help='Stage the redesigned Controls resources only')
    mode.add_argument('--store-ui-only', action='store_true', help='Stage only App Store layout resources')
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
        version = current['firmware_version']
        if version not in ('0.8.3-s3.84', '0.8.3-s3.85', '0.8.3-s3.86', '0.8.3-s3.87', '0.8.3-s3.88', '0.8.3-s3.89', '0.8.3-s3.90') or current['screen_locked']:
            raise SystemExit('Start the supported firmware and unlock the screen before installing these resources')
        app_ui = version in ('0.8.3-s3.86', '0.8.3-s3.87', '0.8.3-s3.88', '0.8.3-s3.89', '0.8.3-s3.90')
        controls_ui = version in ('0.8.3-s3.88', '0.8.3-s3.89', '0.8.3-s3.90')
        store_ui = version == '0.8.3-s3.90'
        full = not (args.apps_ui_only or args.controls_ui_only or args.store_ui_only)
        if args.apps_ui_only and not app_ui:
            raise SystemExit('The Files layout requires firmware s3.86')
        if args.controls_ui_only and not controls_ui:
            raise SystemExit('The redesigned Controls layout requires firmware s3.88')
        if args.store_ui_only and not store_ui:
            raise SystemExit('The redesigned App Store layout requires firmware s3.90')
        local = Path(temp)
        originals = []
        files = {}

        def read_json(path):
            return json.loads(storage('FSReadText', Path=path))

        def modified(name, doc):
            path = local / name
            path.write_bytes((json.dumps(doc, ensure_ascii=False, separators=(',', ':')) + '\n').encode())
            return path

        if full:
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

        if app_ui and (full or args.apps_ui_only):
            for path in sorted(APP_UI.rglob('*')):
                if not path.is_file():
                    continue
                group, relative = path.relative_to(APP_UI).as_posix().split('/', 1)
                target = (SHELL if group == 'shell' else FILES_APP) + '/' + relative
                files[target] = path

        if controls_ui and (full or args.controls_ui_only):
            # Publish the root after its assets have been staged and verified.
            paths = sorted((p for p in CONTROL_UI.rglob('*') if p.is_file()),
                           key=lambda p: (p == CONTROL_UI / 'root.json', p))
            for path in paths:
                files[CONTROLS + '/' + path.relative_to(CONTROL_UI).as_posix()] = path

        if store_ui and (full or args.store_ui_only):
            installed = call('SystemCore', 'ListApps')
            store = next(app for app in installed if app['manifest']['id'] == 'brookesia.general.app_store')
            if call('SystemCore', 'GetActiveApp').get('app_id') == store['app_id']:
                raise SystemExit('Return to the desktop before updating App Store resources')
            hashes = json.loads((ROOT / 'tools/build-inputs.json').read_bytes())['sha256']
            for name in ('constants/480x480.json', 'screens/app_store.json', 'templates/app_store_item.json'):
                source = STORE_UI / name
                if hashlib.sha256(source.read_bytes()).hexdigest() != hashes[source.relative_to(ROOT).as_posix()]:
                    raise SystemExit(f'App Store resource checksum mismatch: {name}')
                files[f'{STORE_APP}/{name}'] = source

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
        verified = stage + '/verified'
        storage('FSMkdir', Path=verified)
        expected = {}
        try:
            for index, (target, path, staged, original) in enumerate(originals):
                written.append((target, original))
                storage('FSCopyTree', From=staged, To=target, Overwrite=True)
                assert storage('FSStat', Path=target)['size'] == path.stat().st_size, target
                name = str(index)
                storage('FSCopyTree', From=target, To=f'{verified}/{name}', Overwrite=False)
                expected[name] = path.read_bytes()
            result = call('SdResources', 'InspectTree', Path=verified)
            assert result['sha256'] == tree_hash(expected), 'Installed resource checksum mismatch'
        except Exception:
            for target, original in reversed(written):
                if original:
                    storage('FSCopyTree', From=original, To=target, Overwrite=True)
                else:
                    storage('FSRemove', Path=target)
            raise
        if not controls_ui and current['desktop_theme_index'] < 2:
            call('DeviceModes', 'SetDesktopTheme', Index=2)
            time.sleep(3)
        print(f'Installed and verified {len(files)} resources. Previous files saved under {stage}.')


if __name__ == '__main__':
    main()
