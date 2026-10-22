"""Add a safe motion margin to an installed cream wallpaper, preserving its source."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

from verify_child_mode import Client

ROOT = Path(__file__).resolve().parents[1]
BACKGROUND = '/littlefs/system/super/shell/screens/background.json'
STYLES = '/littlefs/system/super/shell/styles/cream.json'
IMAGES = '/littlefs/system/super/shell/images/index.json'
FLASH = '/littlefs/themes/cream-handdrawn-v1'
SD = '/sdcard/themes/cream-handdrawn-v1'


class WallpaperClient(Client):
    def read_json(self):
        value = super().read_json()
        # The protocol permits smaller payloads than its advertised maximum.
        # Bound UART bursts while GUI rendering and Flash writes share the CPU.
        if 'max_frame_payload' in value:
            value['max_frame_payload'] = min(value['max_frame_payload'], 2048)
        return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--theme', type=Path, default=ROOT.parent/'themes/cream-handdrawn-v1')
    args = parser.parse_args()
    manifest = json.loads((args.theme/'theme.json').read_text(encoding='utf-8'))
    name = manifest['wallpaper_render']
    assert Path(name).name == name and name == 'wallpaper-486-rgb565.bin'
    asset = args.theme/name
    data = asset.read_bytes()
    assert len(data) == manifest['files'][name]['bytes'] and 24 < len(data) < 472404
    assert hashlib.sha256(data).hexdigest() == manifest['files'][name]['sha256']
    with WallpaperClient(args.port, timeout=25) as client:
        client.hello()
        def call(name, params):
            return client.call('Storage', name, params)['result']
        original = call('FSReadText', {'Path': BACKGROUND})
        original_styles = call('FSReadText', {'Path': STYLES})
        styles = json.loads(original_styles)
        original_images = call('FSReadText', {'Path': IMAGES})
        images = json.loads(original_images)
        background = json.loads(original)
        wallpaper = next((n for n in background.get('children', [])
                          if n.get('id') == 'cream_wallpaper' and n.get('type') == 'image'), None)
        if wallpaper is None:
            raise SystemExit('Install the cream desktop theme before enabling wallpaper motion.')
        assert wallpaper.get('imageProps', {}).get('innerAlign') == 'cover'
        folder = ROOT / 'runtime' / ('wallpaper-backup-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
        folder.mkdir(parents=True)
        (folder / 'background-before.json').write_text(original, encoding='utf-8')
        (folder / 'cream-before.json').write_text(original_styles, encoding='utf-8')
        (folder / 'images-before.json').write_text(original_images, encoding='utf-8')
        result = client.transfer('put', asset, 'wallpaper-render.bin', True)
        assert result['ok'], result
        call('FSRename', {'From': '/littlefs/usb/wallpaper-render.bin', 'To': FLASH+'/'+name})
        on_sd = call('FSStat', {'Path': '/sdcard'})['exists']
        if on_sd:
            call('FSMkdir', {'Path': SD})
            call('FSCopyTree', {'From': FLASH+'/'+name, 'To': SD+'/'+name, 'Overwrite': True})
            assert call('FSStat', {'Path': SD+'/'+name})['size'] == len(data)
        # bgOpacity is not a supported style field. An empty color makes only
        # the launcher surfaces transparent, revealing the wallpaper beneath.
        desktop = styles['styles']['shell.desktop']
        desktop['bgColor'] = ''
        desktop.pop('bgOpacity', None)
        wallpaper.setdefault('placement', {}).update(mode='absolute', x=-3, y=-3, width=486, height=486)
        wallpaper.setdefault('bindings', {}).update({'placement.x': 'wallpaper_x', 'placement.y': 'wallpaper_y'})
        local = folder / 'background-after.json'
        local.write_text(json.dumps(background, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
        # Stay within the existing USB staging boundary; rename only after
        # the transfer's integrity check succeeds.
        result = client.transfer('put', local, 'wallpaper-update.json', True)
        assert result['ok'], result
        call('FSRename', {'From': '/littlefs/usb/wallpaper-update.json', 'To': BACKGROUND})
        assert json.loads(call('FSReadText', {'Path': BACKGROUND})) == background
        style_local = folder / 'cream-after.json'
        style_local.write_text(json.dumps(styles, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
        result = client.transfer('put', style_local, 'wallpaper-style.json', True)
        assert result['ok'], result
        call('FSRename', {'From': '/littlefs/usb/wallpaper-style.json', 'To': STYLES})
        assert json.loads(call('FSReadText', {'Path': STYLES})) == styles
        wallpaper_image = next(n for n in images['images'] if n['id'] == 'cream.wallpaper')
        wallpaper_image.update(src=FLASH+'/'+name, width=486, height=486)
        images_local = folder/'images-after.json'
        images_local.write_text(json.dumps(images, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
        result = client.transfer('put', images_local, 'wallpaper-images.json', True)
        assert result['ok'], result
        call('FSRename', {'From': '/littlefs/usb/wallpaper-images.json', 'To': IMAGES})
        assert json.loads(call('FSReadText', {'Path': IMAGES})) == images
        print(json.dumps({'backup': str(folder), 'restart_required': True, 'interval_seconds': 60,
                          'max_offset_pixels': 3, 'native_rgb565': True, 'on_sd': on_sd}, ensure_ascii=False))


if __name__ == '__main__':
    main()
