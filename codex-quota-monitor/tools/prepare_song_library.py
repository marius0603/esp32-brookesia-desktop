"""Download page-linked nursery songs privately and verify encoded loudness.

The manifest records source and output hashes. Audio is never included in Git.
Use --record once when reviewing a new selection; subsequent runs verify hashes.
"""
import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path
from normalize_story_audio import normalize

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--ffmpeg', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--record', action='store_true')
    a = p.parse_args()
    output = a.output.resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT/'codex-quota-monitor/runtime'):
        raise SystemExit('Keep downloaded recordings outside Git')
    output.mkdir(parents=True, exist_ok=True)
    m = json.loads(a.manifest.read_text(encoding='utf-8'))
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    encoder = digest(a.ffmpeg)
    if not a.record:
        assert encoder == m['ffmpeg']['sha256'], 'Use the pinned encoder'
    m['ffmpeg'] = {'build': a.ffmpeg.name, 'sha256': encoder}
    for r in m['songs']:
        assert Path(r['filename']).name == r['filename'] and r['filename'].endswith('.mp3')
        u = urllib.parse.urlsplit(r['download'])
        assert u.scheme == 'https'
        if u.hostname == 'cdnwukong.com':
            assert u.path.startswith('/public/blog/wp-content/uploads/2024/07/')
        elif u.hostname in ('orangefreesounds.com','www.orangefreesounds.com'):
            assert u.path.startswith('/wp-content/uploads/') and u.path.endswith('.mp3')
            assert r['artist']=='Alexander Blu' and r['license'] in ('CC-BY-4.0','CC-BY-NC-4.0')
        else:
            raise AssertionError('Unreviewed audio host')
        raw = output/('raw-'+r['filename'])
        out = output/('normalized-'+r['filename'])
        if not raw.exists():
            url = urllib.parse.urlunsplit((u.scheme,u.netloc,urllib.parse.quote(urllib.parse.unquote(u.path)),u.query,''))
            request = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(request, timeout=90) as response:
                data = response.read(32*1024*1024+1)
            assert 1000 < len(data) <= 32*1024*1024
            if not a.record:
                assert len(data)==r['raw_bytes'] and hashlib.sha256(data).hexdigest()==r['raw_sha256']
            raw.write_bytes(data)
        if not a.record:
            assert raw.stat().st_size==r['raw_bytes'] and digest(raw)==r['raw_sha256']
        if not out.exists():
            normalize(a.ffmpeg,raw,out,m['target_lufs'])
        measured = json.loads(out.with_suffix('.loudness.json').read_text(encoding='utf-8'))
        assert measured['input_sha256']==digest(raw) and measured['sha256']==digest(out)
        assert abs(float(measured['after']['input_i'])-m['target_lufs'])<=0.35
        assert float(measured['after']['input_tp'])<=-0.8
        values = {'raw_bytes':raw.stat().st_size,'raw_sha256':digest(raw),
                  'bytes':out.stat().st_size,'sha256':digest(out),
                  'loudness_lufs':float(measured['after']['input_i']),
                  'true_peak_dbtp':float(measured['after']['input_tp']),
                  'duration_seconds':measured['duration_seconds'],
                  'duration_difference_seconds':measured['duration_difference_seconds'],
                  'stereo_cancellation_corrected':measured['stereo_cancellation_corrected']}
        if not a.record:
            for key,value in values.items(): assert r[key]==value, (r['title'],key)
        r.update(values)
        if a.record:
            a.manifest.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Verified '+r['title']+' '+str(r['loudness_lufs'])+' LUFS',flush=True)


if __name__ == '__main__': main()
