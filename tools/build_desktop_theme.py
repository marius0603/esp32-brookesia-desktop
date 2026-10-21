"""Export generated artwork at device resolution without changing the artwork."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ICONS = {
    'brookesia.general.settings': 'settings',
    'brookesia.general.files': 'files',
    'brookesia.general.app_store': 'app-store',
    'local.codex.quota': 'quota',
    'local.weather': 'weather',
    'local.audiobook': 'audiobook',
    'local.flipclock': 'flipclock',
    'local.voiceassistant': 'assistant',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'themes/cream-handdrawn-v1')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    assets = []
    for name in ICONS.values():
        target = args.output / f'{name}.png'
        with Image.open(args.source / f'{name}.png') as image:
            image.convert('RGBA').resize((96, 96), Image.Resampling.LANCZOS).save(target, optimize=True)
        assets.append(target)
    wallpaper = args.output / 'wallpaper.jpg'
    with Image.open(args.source / 'wallpaper.png') as image:
        image.convert('RGB').resize((480, 480), Image.Resampling.LANCZOS).save(
            wallpaper, quality=88, subsampling=0, optimize=True)
    assets.append(wallpaper)
    manifest = {
        'id': 'cream-handdrawn-v1', 'display': [480, 480], 'icon_size': [96, 96],
        'icons': {app: f'{name}.png' for app, name in ICONS.items()},
        'wallpaper': 'wallpaper.jpg',
        'files': {p.name: {'bytes': p.stat().st_size,
                         'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in assets},
    }
    (args.output / 'theme.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'asset_bytes': sum(p.stat().st_size for p in assets)}, indent=2))


if __name__ == '__main__':
    main()
