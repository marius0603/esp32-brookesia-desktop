"""Deploy a reversible Shell-only theme through the existing USB Storage service.

Upload images before switching descriptors. Save every replaced JSON locally;
the original image files, app code, app data and NVS remain untouched.
Restart the device separately after successful deployment.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quota_monitor.brookesia import StableUsbClient

SHELL = '/littlefs/system/super/shell'


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('theme', type=Path, nargs='?')
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--restore', type=Path, help='Restore a deployment backup directory')
    args = parser.parse_args()
    with StableUsbClient(args.port, timeout=25) as client:
        client.hello()
        def call(name, params):
            return client.call('Storage', name, params)['result']
        def upload(local, remote):
            # USB restricts uploads to /littlefs/usb. Move the verified staged
            # file with Storage rather than weakening that upload boundary.
            stage = 'theme-stage/' + local.name
            result = client.transfer('put', local, stage, True)
            assert result['ok'] is True, result
            call('FSRename', {'From': '/littlefs/usb/' + stage, 'To': remote})
            return result
        def put_json(remote, obj, folder, index):
            local = folder / f'update-{index:02d}.json'
            dump(local, obj)
            # Binary put supports JSON larger than the USB command size limit.
            result = upload(local, remote)
            assert result['ok'] is True, result
        if args.restore:
            originals = json.loads((args.restore / 'original-resources.json').read_text(encoding='utf-8'))
            for index, (path, text) in enumerate(originals.items()):
                put_json(path, json.loads(text), args.restore, index)
            print('Original descriptors restored; restart the device to apply.')
            return
        if args.theme is None:
            parser.error('theme directory or --restore is required')
        manifest = json.loads((args.theme / 'theme.json').read_text(encoding='utf-8'))
        assert manifest['id'] == 'cream-handdrawn-v1'
        base = '/littlefs/themes/' + manifest['id']
        for name, info in manifest['files'].items():
            assert Path(name).name == name
            data = (args.theme / name).read_bytes()
            assert len(data) == info['bytes'] and hashlib.sha256(data).hexdigest() == info['sha256']
        env = client.call('SystemCore', 'GetEnvironment', {})['result']
        assert [env['width_px'], env['height_px']] == manifest['display'], env
        apps = client.call('SystemCore', 'ListApps', {})['result']
        assert set(manifest['icons']).issubset(a['manifest']['id'] for a in apps)
        active = client.call('SystemCore', 'GetActiveApp', {})['result']
        if active.get('manifest', {}).get('id') not in (None, 'brookesia.system.super.shell'):
            client.call('SystemCore', 'RequestCloseApp', {'AppId': active['app_id']})
        backup = ROOT / 'runtime' / ('theme-backup-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
        backup.mkdir(parents=True)
        dump(backup / 'apps-before.json', apps)
        dump(backup / 'environment-before.json', env)
        originals = {}
        paths = [f'/littlefs/apps/{app}/res/images/index.json' for app in manifest['icons']]
        paths += [f'{SHELL}/root.json', f'{SHELL}/images/index.json', f'{SHELL}/screens/background.json']
        for path in paths:
            originals[path] = call('FSReadText', {'Path': path})
            dump(backup / 'original-resources.json', originals)
        capacity = call('GetFileSystemCapacity', {'MountPoint': '/littlefs'})
        additional = 0
        for name, info in manifest['files'].items():
            existing = call('FSStat', {'Path': f'{base}/{name}'})
            additional += max(0, info['bytes'] - (existing['size'] if existing['exists'] else 0))
        # Include transfer/JSON staging and a separate metadata/GC reserve.
        needed = additional + 65536
        assert capacity['free_bytes'] >= needed + 65536, (capacity, needed)
        call('FSMkdir', {'Path': base})
        call('FSMkdir', {'Path': f'{SHELL}/styles'})
        report = {'backup': str(backup), 'capacity_before': capacity, 'uploads': [], 'updates': []}
        dump(backup / 'deployment.json', report)
        for name in manifest['files']:
            remote = f'{base}/{name}'
            result = upload(args.theme / name, remote)
            assert result['ok'] is True, result
            report['uploads'].append({'path': remote, 'result': result})
            dump(backup / 'deployment.json', report)
        updates = {}
        for app, name in manifest['icons'].items():
            path = f'/littlefs/apps/{app}/res/images/index.json'
            doc = json.loads(originals[path])
            icon = next(i for i in doc['images'] if i['id'] == 'launcher_icon')
            icon.update(src=f'{base}/{name}', width=96, height=96)
            updates[path] = doc
        path = f'{SHELL}/images/index.json'
        images = json.loads(originals[path])
        images['images'] = [i for i in images['images'] if i['id'] != 'cream.wallpaper']
        images['images'].append({'id': 'cream.wallpaper', 'src': f'{base}/{manifest["wallpaper"]}',
                                 'width': 480, 'height': 480})
        updates[path] = images
        background = json.loads(originals[f'{SHELL}/screens/background.json'])
        background['style'].update(bgColor='#fff1dc', bgOpacity=255)
        background['children'] = [{
            'type': 'image', 'id': 'cream_wallpaper',
            'commonProps': {'clickable': False, 'scrollable': False},
            'placement': {'mode': 'absolute', 'x': 0, 'y': 0, 'width': 'match', 'height': 'match'},
            'imageProps': {'src': '${image.cream.wallpaper}', 'innerAlign': 'cover'},
        }]
        updates[f'{SHELL}/screens/background.json'] = background
        styles = {'type': 'styleSet', 'styles': {
            'shell.desktop': {'bgColor': '#fff1dc', 'bgOpacity': 0},
            'shell.launcherAppLabel': {'textColor': '#42291f', 'fontSize': '12sp'},
            'shell.launcherAppButton': {'bgColor': '', 'bgOpacity': 0, 'borderWidth': '0dp', 'radius': '18dp'},
            'shell.launcherIconTile': {'bgColor': '', 'bgOpacity': 0, 'borderWidth': '0dp',
                                       'radius': '16dp', 'clipCorner': True},
            'shell.statusBar': {'bgColor': '#fff1dc', 'borderColor': '#e7b995', 'borderWidth': '1dp'},
            'shell.statusBrand': {'textColor': '#42291f', 'fontSize': '12sp'},
            'shell.statusTitle': {'textColor': '#775145', 'fontSize': '14sp'},
            'shell.statusTiny': {'textColor': '#42291f', 'fontSize': '10sp'},
            'shell.statusTinyMuted': {'textColor': '#775145', 'fontSize': '10sp'},
            'shell.gestureIndicatorBar': {'bgColor': '#775145', 'opacity': 180, 'radius': '3dp'},
        }}
        updates[f'{SHELL}/styles/cream.json'] = styles
        root = json.loads(originals[f'{SHELL}/root.json'])
        if 'styles/cream.json' not in root['assets']:
            root['assets'].append('styles/cream.json')
        # Commit the root last, after every referenced asset exists.
        updates[f'{SHELL}/root.json'] = root
        for index, (path, doc) in enumerate(updates.items()):
            put_json(path, doc, backup, index)
            report['updates'].append(path)
            dump(backup / 'deployment.json', report)
            readback = json.loads(call('FSReadText', {'Path': path}))
            assert readback == doc, path
        report['capacity_after'] = call('GetFileSystemCapacity', {'MountPoint': '/littlefs'})
        report['complete'] = True
        dump(backup / 'deployment.json', report)
        print(json.dumps({'backup': str(backup), 'updated_descriptors': len(updates),
                          'capacity_after': report['capacity_after'], 'restart_required': True}, indent=2))


if __name__ == '__main__':
    main()
