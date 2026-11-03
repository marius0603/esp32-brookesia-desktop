"""Package the radio UI with all native assets and the generated station catalog."""
import json,subprocess
from pathlib import Path
from build_learning_packages import archive
from runtime_paths import find_node
ROOT=Path(__file__).resolve().parents[2]
def main():
 subprocess.run([find_node(),str(ROOT/'brookesia-apps/radio/tests/main.test.cjs')],check=True)
 src=ROOT/'brookesia-apps/radio/src';version=json.loads((src/'manifest.json').read_text(encoding='utf-8'))['package']['version']
 files={p.relative_to(src).as_posix():p.read_bytes() for p in src.rglob('*') if p.is_file() and p.name!='catalog.js'}
 for name,data in list(files.items()):
  if name.endswith('.json'):files[name]=(json.dumps(json.loads(data),ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
 for item in json.loads(files['res/images/index.json'])['images']:assert 'res/images/'+item['src'] in files
 name='packages/apps/local.radio.debug.'+version+'.bpk';digest=archive(ROOT/name,files)
 path=ROOT/'packages/SHA256.json';hashes=json.loads(path.read_text(encoding='utf-8'));hashes[name]=digest;path.write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(name,digest)
if __name__=='__main__':main()
