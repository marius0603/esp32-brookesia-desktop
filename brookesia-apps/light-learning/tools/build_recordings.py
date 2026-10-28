"""Prepare card audio from hash-verified human recordings; no speech synthesis."""
import argparse,array,hashlib,json,math,shutil,subprocess,sys,tempfile,urllib.request,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def digest(data):return hashlib.sha256(data).hexdigest()

def decode(ffmpeg,path):
    result=subprocess.run([ffmpeg,'-nostdin','-v','error','-i',str(path),'-ac','1','-ar','16000','-f','s16le','pipe:1'],check=True,capture_output=True)
    values=array.array('h');values.frombytes(result.stdout)
    if sys.byteorder!='little':values.byteswap()
    assert 1600<=len(values)<=16000*8,'Unexpected recording length'
    peak=max(abs(v) for v in values);rms=math.sqrt(sum(v*v for v in values)/len(values))
    assert peak>100 and rms>30,'Silent source recording'
    gain=min(3.0,6000/rms,26000/peak)
    return array.array('h',(round(v*gain) for v in values))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ffmpeg',default=shutil.which('ffmpeg'))
    p.add_argument('--cache',type=Path,default=Path(tempfile.gettempdir())/'light-learning-recordings')
    args=p.parse_args();assert args.ffmpeg,'Install ffmpeg or provide --ffmpeg'
    path=ROOT/'packs/audio-sources.json';metadata=json.loads(path.read_text(encoding='utf-8'))
    assert metadata['schema']==1 and metadata['voice_type']=='human_recording'
    args.cache.mkdir(parents=True,exist_ok=True);pcm={}
    for recording in metadata['recordings']:
        local=args.cache/recording['file']
        if not local.exists():
            request=urllib.request.Request(recording['download_url'],headers={'User-Agent':'LightLearningRecordingBuilder/1.2'})
            with urllib.request.urlopen(request,timeout=40) as response:data=response.read(2*1024*1024)
            assert digest(data)==recording['sha256'],'Source hash mismatch'
            local.write_bytes(data)
        assert digest(local.read_bytes())==recording['sha256'],recording['id']
        pcm[recording['id']]=decode(args.ffmpeg,local)
    pause_frames=metadata['separator_ms']*16
    metadata['outputs']={}
    for card in metadata['cards']:
        chinese=pcm[card['chinese']];english=pcm[card['english']]
        samples=chinese+array.array('h',[0])*pause_frames+english
        destination=ROOT/'packs/starter'/card['file']
        if sys.byteorder!='little':samples.byteswap()
        with wave.open(str(destination),'wb') as output:
            output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000);output.writeframes(samples.tobytes())
        metadata['outputs'][card['file']]={'chinese_frames':len(chinese),'pause_frames':pause_frames,'english_frames':len(english),'sha256':digest(destination.read_bytes())}
    path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(str(len(metadata['cards']))+' card recordings built: human Mandarin, pause, human English; no TTS, speed or pitch changes.')

if __name__=='__main__':main()
