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
args = parser.parse_args()
app = args.app.resolve()
node = find_node()
cli = ROOT/'tools/brookesia-toolkit/node_modules/esp-brookesia-toolkit/dist/bin.mjs'
source = json.loads((app/'src/manifest.json').read_text(encoding='utf-8'))
subprocess.run([str(node), str(cli), 'build'], cwd=app, check=True)
manifest = json.loads((app/'build/manifest.json').read_text(encoding='utf-8'))
manifest['services'] = source.get('services', [])
(app/'build/manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
output = app/'dist'/f"{source['package']['id']}.debug.{source['package']['version']}.bpk"
subprocess.run([str(node), str(cli), 'pack', '--source-dir', 'build', '--output', str(output)], cwd=app, check=True)
with zipfile.ZipFile(output) as archive:
    assert archive.testzip() is None
    assert json.loads(archive.read('manifest.json'))['services'] == source.get('services', [])
print(output)
