"""Measure all six playback rates on a temporary, four-second SD WAV."""
import argparse,json,math,struct,time,wave
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);a=p.parse_args()
 runtime=ROOT/'runtime';runtime.mkdir(exist_ok=True)
 audio=runtime/'speed-check.wav'
 with wave.open(str(audio),'wb') as w:
  w.setparams((1,2,16000,0,'NONE','not compressed'))
  w.writeframes(b''.join(struct.pack('<h',round(1000*math.sin(2*math.pi*220*i/16000))) for i in range(64000)))
 report={'passed':False,'rates':[]};remote='/sdcard/audiobooks/__speed_check.wav'
 with StoryClient(a.port,timeout=30) as c:
  c.hello()
  def f(s,n,p=None):return c.call(s,n,p or {})['result']
  before=f('Audiobook','GetState');modes=f('DeviceModes','GetState')
  assert not before['sleep_active'] and not modes['screen_locked']
  assert before['speed']==1,'A fresh boot must default to 1x'
  app=next(x for x in f('SystemCore','ListApps') if x['manifest']['id']=='local.audiobook')
  saved={n:f('Storage','FSReadText',{'Path':n}) for n in ['/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json']}
  tracks=f('Audiobook','List')['tracks'];volume=modes['resume_volume']
  def wait(test,seconds=25):
   end=time.monotonic()+seconds
   while time.monotonic()<end:
    s=f('Audiobook','GetState');assert not s['error'],s['error']
    if test(s):return s
    time.sleep(.08)
   raise TimeoutError('Playback state timeout')
  try:
   f('SystemCore','StopApp',{'AppId':app['app_id']})
   result=c.transfer('put',audio,'sd-audiobooks/__speed_check.wav',False);assert result['ok']
   f('AudioPlayback','SetVolume',{'Volume':0})
   for invalid in [0,0.6,3]:
    try:c.call('Audiobook','SetSpeed',{'Speed':invalid})
    except Exception:pass
    assert f('Audiobook','GetState')['speed']==1
   for speed in [.5,.75,1,1.25,1.5,2]:
    f('Audiobook','SetSpeed',{'Speed':speed});assert f('Audiobook','GetState')['speed']==speed
    began=time.monotonic();f('Audiobook','Play',{'Path':remote,'Position':0})
    state=wait(lambda s:s['state']=='Ended' and not s['active'])
    elapsed=time.monotonic()-began;expected=4/speed
    assert abs(state['bytes_written']/(64000*expected)-1)<.07,(speed,state)
    assert abs(elapsed-expected)<1.3,(speed,elapsed)
    assert state['pcm_starvations']==0,state
    report['rates'].append({'speed':speed,'elapsed_seconds':round(elapsed,3),'pcm_bytes':state['bytes_written'],'starvations':state['pcm_starvations'],'stack_free':state['pcm_stack_free_min_bytes']})
    print(report['rates'][-1],flush=True)
   f('Audiobook','Play',{'Path':remote,'Position':0});wait(lambda s:s['bytes_written']>10000)
   f('Audiobook','Pause');time.sleep(.2);paused=f('Audiobook','GetState')['bytes_written'];f('Audiobook','SetSpeed',{'Speed':.75});time.sleep(.3)
   assert f('Audiobook','GetState')['bytes_written']==paused
   f('Audiobook','Seek',{'Seconds':1});f('Audiobook','Resume');wait(lambda s:s['state']=='Ended')
   report['passed']=True
  finally:
   f('Audiobook','Stop');f('Audiobook','SetSpeed',{'Speed':1})
   f('Storage','FSRemove',{'Path':remote})
   for name,text in saved.items():f('Storage','FSWriteText',{'Path':name,'Data':text})
   f('AudioPlayback','SetVolume',{'Volume':volume})
   assert f('Audiobook','List')['tracks']==tracks
   (runtime/'audiobook-speed-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Playback speed verification:',report['passed'],flush=True)

if __name__=='__main__':main()
