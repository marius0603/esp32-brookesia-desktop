"""Make compact, matching Flash fallbacks for the SD-first desktop theme."""
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
theme = ROOT / 'themes/cream-handdrawn-v1'
output = theme / 'flash-fallback'
output.mkdir(exist_ok=True)
manifest = json.loads((theme / 'theme.json').read_text(encoding='utf-8'))
files = {}
for name in manifest['icons'].values():
    target = output / name
    with Image.open(theme / name) as image:
        image.convert('RGBA').quantize(colors=64, method=Image.Quantize.FASTOCTREE,
                                       dither=Image.Dither.NONE).save(target, optimize=True)
    files[name] = {'bytes': target.stat().st_size,
                   'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
(output / 'manifest.json').write_text(json.dumps({'files': files}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'files': len(files), 'bytes': sum(item['bytes'] for item in files.values())}))
