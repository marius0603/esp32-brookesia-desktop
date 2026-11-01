"""Exercise continuous PCM supply, including deliberate 200ms decoder stalls."""
import argparse,json,time
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',required=True);a=p.parse_args()
    report={'passed':False,'samples':[]}
    output=ROOT/'runtime/audiobook-buffer-verification.json'
    with StoryClient(a.port,timeout=30) as c:
        c.hello()
        print('USB ready; checking buffered playback.',flush=True)
        def f(s,n,p=None):return c.call(s,n,p or {})['result']
        def wait(predicate,seconds=20):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                value=f('Audiobook','GetState');assert not value['error'],value['error']
                if predicate(value):return value
                time.sleep(.15)
            raise TimeoutError('Audiobook state did not reach the expected condition')
        before=f('DeviceModes','GetState');volume=before['resume_volume']
        tracks=f('Audiobook','List')['tracks'];assert len(tracks)==20
        app=next(x for x in f('SystemCore','ListApps') if x['manifest']['id']=='local.audiobook')
        saved={p:f('Storage','FSReadText',{'Path':p}) for p in ('/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json')}
        mode=json.loads(saved['/littlefs/audiobook-play-mode.json'])['mode']
        bookmark=json.loads(saved['/littlefs/audiobook-bookmark.json'])
        try:
            f('DeviceModes','Wake');f('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
            f('SystemCore','StartApp',{'AppId':app['app_id']})
            f('AudioPlayback','SetVolume',{'Volume':0})
            for suffix in ('08-xiaoma-guohe.mp3','小公鸡和小鸭子.mp3','小壁虎借尾巴.mp3'):
                track=next(t for t in tracks if t['path'].endswith('/'+suffix))
                print('Testing '+track['title'],flush=True)
                f('Audiobook','TestDecodeDelay',{'Milliseconds':200})
                f('Audiobook','Play',{'Path':track['path'],'Position':0})
                wait(lambda s:s['state']=='Playing' and s['bytes_written']>32000)
                started=time.monotonic();end=started+15;switched=False
                while time.monotonic()<end:
                    state=wait(lambda s:s['state']=='Playing')
                    assert state['pcm_starvations']==0,state
                    if not switched and time.monotonic()-started>5:
                        f('Audiobook','SetPlayMode',{'Mode':'random'})
                        assert f('Audiobook','GetState')['path']==track['path']
                        switched=True
                    time.sleep(.2)
                assert state['decode_max_us']>=180000,state
                assert state['write_gap_max_us']<30000 and state['pcm_stack_free_min_bytes']>=2048,state
                report['samples'].append({'title':track['title'],**{k:state[k] for k in ('pcm_starvations','write_gap_max_us','decode_max_us','pcm_stack_free_min_bytes','bytes_written')}})
                f('Audiobook','Pause');time.sleep(.2);paused=f('Audiobook','GetState');time.sleep(.4)
                assert f('Audiobook','GetState')['bytes_written']==paused['bytes_written']
                f('Audiobook','Seek',{'Seconds':20});wait(lambda s:s['position']==20)
                f('Audiobook','Resume');wait(lambda s:s['state']=='Playing' and s['position']>=21)
                f('Audiobook','Stop');print('Buffered playback passed: '+track['title'],flush=True)
            f('Audiobook','TestDecodeDelay',{'Milliseconds':0})
            for mode_value in ('random','repeat_one','sequence'):
                f('Audiobook','SetPlayMode',{'Mode':mode_value})
                assert f('Audiobook','GetState')['play_mode']==mode_value
                assert json.loads(f('Storage','FSReadText',{'Path':'/littlefs/audiobook-play-mode.json'}))['mode']==mode_value
            f('Audiobook','Play',{'Path':tracks[0]['path'],'Position':0});wait(lambda s:s['bytes_written']>32000)
            f('Audiobook','TestSleepTimer');wait(lambda s:s['state']=='SleepEnded' and not s['active'],25)
            time.sleep(1.3);assert f('Audiobook','GetState')['state']=='SleepEnded'
            report['sleep_stopped']=True;report['passed']=True
        finally:
            f('Audiobook','TestDecodeDelay',{'Milliseconds':0})
            f('SystemCore','StopApp',{'AppId':app['app_id']});f('Audiobook','Stop')
            f('Audiobook','SetPlayMode',{'Mode':mode})
            for path,text in saved.items():f('Storage','FSWriteText',{'Path':path,'Data':text})
            f('DeviceModes','Wake');f('SystemCore','StartApp',{'AppId':app['app_id']})
            f('Audiobook','Play',{'Path':bookmark['path'],'Position':bookmark.get('position',0)})
            wait(lambda s:s['state']=='Playing' and s['bytes_written']>0)
            f('AudioPlayback','SetVolume',{'Volume':volume})
            f('DeviceModes','SetAutoDeepSleep',{'Minutes':before['auto_deep_sleep_minutes']})
            assert f('Audiobook','List')['tracks']==tracks
            report['restored_volume']=f('DeviceModes','GetState')['resume_volume']
            output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
