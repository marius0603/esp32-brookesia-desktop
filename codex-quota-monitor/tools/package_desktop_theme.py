"""Package native desktop artwork and its font; keep all source art in Git."""
import hashlib,json
from pathlib import Path
from build_learning_packages import archive
ROOT=Path(__file__).resolve().parents[2]
def main():
    folder=ROOT/'themes/cyberpunk-v1';manifest=json.loads((folder/'theme.json').read_text(encoding='utf-8'))
    files={}
    for name,meta in manifest['files'].items():
        data=(folder/name).read_bytes();assert len(data)==meta['bytes'] and hashlib.sha256(data).hexdigest()==meta['sha256'];files[name]=data
    files['theme.json']=(folder/'theme.json').read_bytes()
    for name in ('font-source.json','OFL.txt'):files[name]=(folder/name).read_bytes()
    files['desktop-theme-extra.ttf']=(ROOT/'platform/super_s3_216/littlefs/system/fonts/desktop-theme-extra.ttf').read_bytes()
    files['README.txt']=b'Cyberpunk desktop theme 1.0.0 for s3.31.\nUse tools/deploy_desktop_themes.py from this repository; restart to load images and fonts.\nSettings > Display > Desktop theme: Q / Cyberpunk.\nArtwork is preloaded into RAM. Missing SD assets fall back to the original Q artwork.\n'
    name='packages/resources/cyberpunk-desktop-1.0.0.zip';digest=archive(ROOT/name,files)
    p=ROOT/'packages/SHA256.json';hashes=json.loads(p.read_text(encoding='utf-8'));hashes[name]=digest
    fw='packages/firmware/brookesia-0.8.3-s3.31-app-only.zip'
    if (ROOT/fw).exists():hashes[fw]=hashlib.sha256((ROOT/fw).read_bytes()).hexdigest()
    p.write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(name,digest)
if __name__=='__main__':main()
