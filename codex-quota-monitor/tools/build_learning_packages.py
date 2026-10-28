"""Build the two apps and a separately installable SD content pack."""
import hashlib
import json
from pathlib import Path
import subprocess
import wave
import zipfile
from runtime_paths import find_node
ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'brookesia-apps/light-learning'

def archive(output,files):
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,data)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
    return hashlib.sha256(output.read_bytes()).hexdigest()

def main():
    subprocess.run([find_node(),str(APP/'tests/main.test.cjs')],check=True,cwd=ROOT)
    hashes=json.loads((ROOT/'packages/SHA256.json').read_text(encoding='utf-8'))
    for folder in ('light-learning','child-mode'):
        src=ROOT/'brookesia-apps'/folder/'src'
        manifest=json.loads((src/'manifest.json').read_text(encoding='utf-8'))['package']
        name='packages/apps/'+manifest['id']+'.debug.'+manifest['version']+'.bpk'
        hashes[name]=archive(ROOT/name,{p.relative_to(src).as_posix():p.read_bytes() for p in src.rglob('*') if p.is_file()})
    files={'index.json':(APP/'packs/index.json').read_bytes()}
    pack=json.loads((APP/'packs/starter/pack.json').read_text(encoding='utf-8'))
    files['packs/starter/pack.json']=(APP/'packs/starter/pack.json').read_bytes()
    for item in pack['cards']+pack['english']:
        path=APP/'packs/starter'/item['audio']
        with wave.open(str(path),'rb') as w:
            assert w.getnchannels()==1 and w.getsampwidth()==2 and w.getframerate()==16000
            assert 0<w.getnframes()<=16000*20,path
        files['packs/starter/'+item['audio']]=path.read_bytes()
    for item in pack['cards']:
        files['packs/starter/'+item['image']]=(APP/'packs/starter'/item['image']).read_bytes()
    for filename in ('photo-sources.json','PHOTO-CREDITS.json','audio-sources.json'):
        if (APP/'packs'/filename).exists():files[filename]=(APP/'packs'/filename).read_bytes()
    if 'audio-sources.json' in files:
        voices=json.loads(files['audio-sources.json'])
        assert voices['voice_type']=='human_recording' and len(voices['cards'])==6
        for card in voices['cards']:
            name='packs/starter/'+card['file'];meta=voices['outputs'][card['file']]
            assert hashlib.sha256(files[name]).hexdigest()==meta['sha256']
            with wave.open(str(APP/'packs/starter'/card['file']),'rb') as audio:
                assert audio.getnframes()==meta['chinese_frames']+meta['pause_frames']+meta['english_frames']
                chinese=audio.readframes(meta['chinese_frames']);pause=audio.readframes(meta['pause_frames']);english=audio.readframes(meta['english_frames'])
                assert meta['chinese_frames']>=1600 and meta['english_frames']>=1600
                assert any(chinese) and not any(pause) and any(english),'Both recorded languages and their separator are required'
    version=json.loads((APP/'packs/index.json').read_text(encoding='utf-8')).get('version','1.0.0')
    metadata={'schema':1,'version':version,'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()}}
    files['manifest.json']=(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n').encode()
    name='packages/content/learning-starter-'+version+'.zip'
    hashes[name]=archive(ROOT/name,files)
    version=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['firmware']
    firmware='packages/firmware/brookesia-'+version+'-app-only.zip'
    hashes[firmware]=hashlib.sha256((ROOT/firmware).read_bytes()).hexdigest()
    (ROOT/'packages/SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Built learning app, parental controls and checked SD media package.')

if __name__=='__main__':
    main()
