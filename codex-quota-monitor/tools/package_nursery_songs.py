"""Build the independent nursery-song app without bundling downloaded recordings."""
import json
import subprocess
from pathlib import Path
from build_learning_packages import archive
from runtime_paths import find_node

ROOT=Path(__file__).resolve().parents[2]

def main():
    subprocess.run([find_node(),str(ROOT/'brookesia-apps/nursery-songs/tests/main.test.cjs')],check=True)
    hashes=json.loads((ROOT/'packages/SHA256.json').read_text(encoding='utf-8'))
    for folder in ['nursery-songs','child-mode']:
        src=ROOT/'brookesia-apps'/folder/'src'
        manifest=json.loads((src/'manifest.json').read_text(encoding='utf-8'))['package']
        files={p.relative_to(src).as_posix():p.read_bytes() for p in src.rglob('*') if p.is_file() and p.suffix!='.svg'}
        for name in list(files):
            if name.endswith('.json'):files[name]=(json.dumps(json.loads(files[name]),ensure_ascii=False,separators=(',',':'))+'\n').encode()
        name='packages/apps/'+manifest['id']+'.debug.'+manifest['version']+'.bpk'
        hashes[name]=archive(ROOT/name,files)
        print(name,hashes[name])
    (ROOT/'packages/SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
