"""Build the three-face clock BPK without modifying system firmware."""
import json,subprocess
from pathlib import Path
from build_learning_packages import archive
from runtime_paths import find_node
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'brookesia-apps/flip-clock'
def main():
 for test in ['main.test.cjs','watchfaces.test.cjs']:subprocess.run([find_node(),str(APP/'tests'/test)],check=True)
 src=APP/'src';v=json.loads((src/'manifest.json').read_text(encoding='utf-8'))['package']['version']
 files={p.relative_to(src).as_posix():p.read_bytes() for p in src.rglob('*') if p.is_file()}
 name='packages/apps/local.flipclock.debug.'+v+'.bpk';digest=archive(ROOT/name,files)
 p=ROOT/'packages/SHA256.json';d=json.loads(p.read_text(encoding='utf-8'));d[name]=digest;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(name,digest)
if __name__=='__main__':main()
