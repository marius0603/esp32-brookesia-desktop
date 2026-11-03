"""Download reviewed source files privately and reproduce verified loudness copies."""
import argparse,hashlib,json,urllib.request
from pathlib import Path
from normalize_story_audio import normalize

ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ffmpeg',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--manifest',type=Path,default=ROOT/'samples/stories/library-20261101.json')
    a=p.parse_args();output=a.output.resolve()
    assert not output.is_relative_to(ROOT) or output.is_relative_to(ROOT/'codex-quota-monitor/runtime'), 'Keep downloaded audio outside Git'
    m=json.loads(a.manifest.read_text(encoding='utf-8'))
    assert hashlib.sha256(a.ffmpeg.read_bytes()).hexdigest()==m['ffmpeg']['sha256'], 'Use the encoder build pinned in the manifest'
    output.mkdir(parents=True,exist_ok=True)
    for r in m['stories']:
        assert Path(r['filename']).name==r['filename']
        raw=output/r.get('raw_filename','raw-'+r['filename']);out=output/('normalized-'+r['filename'])
        if not raw.exists():
            assert r['download'].startswith('https://assets.taozhi.online/_Upload/Files/')
            data=urllib.request.urlopen(r['download'],timeout=90).read()
            assert len(data)==r['raw_bytes'] and hashlib.sha256(data).hexdigest()==r['raw_sha256']
            raw.write_bytes(data)
        assert raw.stat().st_size==r['raw_bytes'] and hashlib.sha256(raw.read_bytes()).hexdigest()==r['raw_sha256']
        if not out.exists():normalize(a.ffmpeg,raw,out,m['target_lufs'])
        assert hashlib.sha256(out.read_bytes()).hexdigest()==r['sha256'], 'Encoded result differs; retain the measurement for review'
        print('Verified '+r['title'],flush=True)

if __name__=='__main__':main()
