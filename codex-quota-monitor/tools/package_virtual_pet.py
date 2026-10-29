"""Package the small app separately from its SD animation resources."""
import hashlib,json,subprocess
from pathlib import Path
from build_learning_packages import archive
from runtime_paths import find_node
ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'brookesia-apps/virtual-pet'
def main():
 subprocess.run([find_node(),str(APP/'tests/main.test.cjs')],check=True,cwd=ROOT)
 src=APP/'src';version=json.loads((src/'manifest.json').read_text(encoding='utf-8'))['package']['version']
 hashes=json.loads((ROOT/'packages/SHA256.json').read_text(encoding='utf-8'))
 name='packages/apps/local.virtualpet.debug.'+version+'.bpk'
 hashes[name]=archive(ROOT/name,{p.relative_to(src).as_posix():p.read_bytes() for p in src.rglob('*') if p.is_file()})
 assert (ROOT/name).stat().st_size<100000,'Keep the app small enough for USB staging on existing Flash'
 content=APP/'content';manifest=json.loads((content/'manifest.json').read_text(encoding='utf-8'))
 assert manifest['decoded_frame_bytes']<=1700000
 files={}
 for name,meta in manifest['files'].items():
  data=(content/name).read_bytes();assert len(data)==meta['bytes'] and hashlib.sha256(data).hexdigest()==meta['sha256'];files[name]=data
 files['manifest.json']=(content/'manifest.json').read_bytes()
 name='packages/content/virtual-pet-xiaoli-'+manifest['version']+'.zip';hashes[name]=archive(ROOT/name,files)
 (ROOT/'packages/SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Pet app and SD animation package verified.')
if __name__=='__main__':main()
