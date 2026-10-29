"""Exercise real EOF transitions with the installed app; restore user state."""
import argparse,json,time,wave,uuid
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--port',required=True)
    args=p.parse_args()
    report={'passed':False,'checks':[]}
    with StoryClient(args.port,timeout=30) as c:
        c.hello()
        def f(s,n,a=None):return c.call(s,n,a or {})['result']
        before=f('Audiobook','GetState');assert not before['sleep_active'],'Wait for the user sleep timer to finish'
        assert not f('DeviceModes','GetState')['screen_locked'],'Unlock before checking'
        volume=f('AudioPlayback','GetVolume');tracks=f('Audiobook','List')['tracks'];assert len(tracks)>=2
        app=next(a for a in f('SystemCore','ListApps') if a['manifest']['id']=='local.audiobook')
        saved={}
        paths=('/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json')
        for path in paths:
            saved[path]=f('Storage','FSReadText',{'Path':path}) if f('Storage','FSStat',{'Path':path})['exists'] else None
        (ROOT/'runtime/audiobook-modes-preservation.json').write_text(json.dumps({'files':saved,'volume':volume,'playback':before},indent=2),encoding='utf-8')
        test_name='000-mode-check-'+uuid.uuid4().hex[:8]+'.wav'
        test_path='/sdcard/audiobooks/'+test_name
        test_file=ROOT/'runtime'/test_name
        with wave.open(str(test_file),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0'*(16000*2*4))
        def stop():f('SystemCore','StopApp',{'AppId':app['app_id']})
        def wait(predicate,seconds=12):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                state=f('Audiobook','GetState');assert not state['error'],state
                if predicate(state):return state
                time.sleep(.2)
            raise AssertionError('Timed out waiting for playback transition: '+str(state))
        def start(mode,track):
            stop();f('Storage','FSWriteText',{'Path':paths[1],'Data':json.dumps({'mode':mode})})
            f('SystemCore','StartApp',{'AppId':app['app_id']});time.sleep(1.2)
            active=f('SystemCore','GetActiveApp');assert active['state']=='Running' and not active['last_error'],active
            f('Audiobook','Play',{'Path':track['path'],'Position':0})
            state=wait(lambda s:s['state']=='Playing' and s['bytes_written']>0)
            duration=state['duration'];assert duration==4
            time.sleep(1.1)  # Allow the app's normal polling to see this track.
            f('Audiobook','Seek',{'Seconds':int(duration)-1})
            return duration
        try:
            f('AudioPlayback','SetVolume',{'Volume':0})
            assert c.transfer('put',test_file,'sd-audiobooks/'+test_name,False)['ok']
            test_track={'path':test_path}
            start('sequence',test_track);wait(lambda s:s['path']==tracks[0]['path'] and s['state']=='Playing')
            report['checks'].append('sequence_next')
            start('random',test_track);wait(lambda s:s['path']!=test_path and s['state']=='Playing')
            report['checks'].append('random_different_story')
            duration=start('repeat_one',test_track);wait(lambda s:s['path']==test_path and s['state']=='Playing' and s['position']>=duration-2)
            wait(lambda s:s['path']==test_path and s['state']=='Playing' and s['position']<duration-3)
            report['checks'].append('repeat_one_restarts_at_zero')
            # Keep repeat-one selected while the native sleep timer completes.
            f('Audiobook','TestSleepTimer');wait(lambda s:s['state']=='SleepEnded' and not s['active'],25)
            time.sleep(1.3);assert f('Audiobook','GetState')['state']=='SleepEnded'
            report['checks'].append('sleep_stops_repeat_one')
            report['passed']=True
        finally:
            stop()
            if f('Storage','FSStat',{'Path':test_path})['exists']:f('Storage','FSRemove',{'Path':test_path})
            for path,data in saved.items():
                if data is None:
                    if f('Storage','FSStat',{'Path':path})['exists']:f('Storage','FSRemove',{'Path':path})
                else:f('Storage','FSWriteText',{'Path':path,'Data':data})
            f('SystemCore','StartApp',{'AppId':app['app_id']})
            if before['active'] and before['path'] and before['path']!='@tone':
                f('Audiobook','Play',{'Path':before['path'],'Position':before['position']})
                wait(lambda s:s['state']=='Playing' and s['bytes_written']>0)
                if before['state']=='Paused':f('Audiobook','Pause')
            f('AudioPlayback','SetVolume',{'Volume':volume})
            assert f('Audiobook','List')['tracks']==tracks and f('AudioPlayback','GetVolume')==volume
            for path,data in saved.items():
                if data is not None:assert f('Storage','FSReadText',{'Path':path})==data,path
            report['stories_preserved']=len(tracks);report['volume_restored']=volume
    (ROOT/'runtime/audiobook-modes-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
if __name__=='__main__':main()
