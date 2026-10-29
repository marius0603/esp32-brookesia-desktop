"""Package the directly interpreted audiobook app and all declared resources."""
import hashlib,json,subprocess
from pathlib import Path
from build_learning_packages import archive
from runtime_paths import find_node
ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'brookesia-apps/audiobook'
def main():
    subprocess.run([find_node(),str(APP/'tests/main.test.cjs')],check=True)
    src=APP/'src';manifest=json.loads((src/'manifest.json').read_text(encoding='utf-8'))['package']
    files={p.relative_to(src).as_posix():p.read_bytes() for p in src.rglob('*') if p.is_file()}
    # Resource whitespace need not consume the device's limited install space.
    for name,data in list(files.items()):
        if name.startswith('res/') and name.endswith('.json'):
            original=json.loads(data)
            files[name]=(json.dumps(original,ensure_ascii=False,separators=(',',':'))+'\n').encode()
            assert json.loads(files[name])==original
    for item in json.loads(files['res/images/index.json'])['images']:
        assert 'res/images/'+item['src'] in files
    name='packages/apps/'+manifest['id']+'.debug.'+manifest['version']+'.bpk'
    digest=archive(ROOT/name,files)
    p=ROOT/'packages/SHA256.json';hashes=json.loads(p.read_text(encoding='utf-8'));hashes[name]=digest
    p.write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(name,digest)
if __name__=='__main__':main()
