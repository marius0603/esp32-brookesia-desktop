"""Build a native-bridge JS app, retaining its explicitly declared services."""
import argparse
import json
from pathlib import Path
import subprocess
import zipfile
from runtime_paths import find_node

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('app', type=Path)
parser.add_argument('--compact-json', action='store_true', help='Compact packaged resource JSON without changing source files')
args = parser.parse_args()
app = args.app.resolve()
node = find_node()
cli = ROOT/'tools/brookesia-toolkit/node_modules/esp-brookesia-toolkit/dist/bin.mjs'
source = json.loads((app/'src/manifest.json').read_text(encoding='utf-8'))
subprocess.run([str(node), str(cli), 'build'], cwd=app, check=True)
manifest = json.loads((app/'build/manifest.json').read_text(encoding='utf-8'))
manifest['services'] = source.get('services', [])
(app/'build/manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
if args.compact_json:
    before = after = 0
    for path in (app/'build/res').rglob('*.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        before += path.stat().st_size
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
        assert json.loads(path.read_text(encoding='utf-8')) == data
        after += path.stat().st_size
    print(f'Resource JSON: {before} -> {after} bytes')
output = app/'dist'/f"{source['package']['id']}.debug.{source['package']['version']}.bpk"
subprocess.run([str(node), str(cli), 'pack', '--source-dir', 'build', '--output', str(output)], cwd=app, check=True)
with zipfile.ZipFile(output) as archive:
    assert archive.testzip() is None
    assert json.loads(archive.read('manifest.json'))['services'] == source.get('services', [])
print(output)
