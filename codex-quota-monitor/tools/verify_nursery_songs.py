"""Real-device catalog, 20 decodes, continuity, EOF modes and sleep checks.

Runs quietly, retains existing story preferences, song bookmark/mode, volume,
auto sleep setting, and returns to the desktop. UI touch quality needs a person.
"""
import argparse
import json
import time
from pathlib import Path
from maintenance_client import MaintenanceClient

ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',default='COM5');a=p.parse_args()
    manifest=json.loads((ROOT/'samples/songs/library-20261104.json').read_text(encoding='utf-8'))
    output=ROOT/'codex-quota-monitor/runtime/nursery-songs-verification.json'
    report={'passed':False,'decodes':[],'checks':[]}
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with MaintenanceClient(a.port,timeout=35) as c:
        c.hello()
        def f(s,n,p=None):return c.call_timeout(s,n,p or {})['result']
        def state():return f('Audiobook','GetState')
        def wait(predicate,seconds=20):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                s=state();assert not s['error'],s
                if predicate(s):return s
                time.sleep(.25)
            raise AssertionError('Playback deadline: '+str(s))
        before=f('DeviceModes','GetState');book=state()
        assert not book['active'] and not book['sleep_active']
        assert not f('Radio','GetState')['active'] and not f('VoiceAssistant','GetState').get('active',False)
        child=f('ChildMode','GetState');assert not child['enabled'],'Do not bypass parent limits for diagnostics'
        stories=f('Audiobook','List')['tracks'];songs=f('Audiobook','ListSongs')['tracks']
        assert len(songs)==20 and len(stories)==30
        assert not {t['path'] for t in stories}&{t['path'] for t in songs}
        assert {t['title'] for t in songs}=={r['title'] for r in manifest['songs']}
        deadline=time.monotonic()+45
        while True:
            apps=f('SystemCore','ListApps');app=next((v for v in apps if v['manifest']['id']=='local.nurserysongs'),None)
            if app:break
            assert time.monotonic()<deadline,'Song app discovery timed out'
            time.sleep(1)
        f('SystemCore','StopApp',{'AppId':app['app_id']})
        song_settings='/sdcard/apps/local.nurserysongs/data/player.json'
        saved={}
        for path in ['/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json',song_settings]:
            saved[path]=f('Storage','FSReadText',{'Path':path}) if f('Storage','FSStat',{'Path':path})['exists'] else None
        def start():
            f('SystemCore','StartApp',{'AppId':app['app_id']});time.sleep(1)
            active=f('SystemCore','GetActiveApp');assert active['state']=='Running' and not active['last_error'],active
        try:
            f('DeviceModes','Wake');f('DeviceModes','SetAutoDeepSleep',{'Minutes':0});f('AudioPlayback','SetVolume',{'Volume':0})
            start();assert not state()['active'];report['checks'].append('silent_start')
            for track in songs:
                f('Audiobook','Play',{'Path':track['path'],'Position':0})
                s=wait(lambda s:s['path']==track['path'] and s['state']=='Playing' and s['bytes_written']>=65536)
                duration=next(r['duration_seconds'] for r in manifest['songs'] if r['title']==track['title'])
                assert abs(s['duration']-duration)<2
                report['decodes'].append({'title':track['title'],'bytes_written':s['bytes_written'],'duration':s['duration']});save()
                f('Audiobook','Stop');print('Decoded '+track['title'],flush=True)
            f('Audiobook','Play',{'Path':songs[0]['path'],'Position':0})
            s=wait(lambda s:s['state']=='Playing' and s['bytes_written']>65536)
            first=s['bytes_written'];start_time=time.monotonic();time.sleep(20);s=state();elapsed=time.monotonic()-start_time
            assert s['state']=='Playing' and not s['error'] and s['pcm_starvations']==0,s
            # The shared mic/speaker clock outputs 16kHz, stereo s16 PCM,
            # independently of the MP3 file's 44.1kHz encoding rate.
            assert s['bytes_written']-first>elapsed*16000*4*.90 and s['write_gap_max_us']<100000,s
            report['continuity']={k:s[k] for k in ['pcm_starvations','write_gap_max_us','decode_max_us','pcm_stack_free_min_bytes']}
            report['checks'].append('20_second_continuous_pcm')
            for mode in ['sequence','random','repeat_one']:
                f('SystemCore','StopApp',{'AppId':app['app_id']})
                f('Storage','FSWriteText',{'Path':song_settings,'Data':json.dumps({'mode':mode,'bookmark':{'path':songs[0]['path'],'position':0}})})
                start();f('Audiobook','Play',{'Path':songs[0]['path'],'Position':0})
                s=wait(lambda s:s['state']=='Playing' and s['bytes_written']>65536);time.sleep(1.3)
                f('Audiobook','Seek',{'Seconds':max(0,s['duration']-1)})
                if mode=='repeat_one':
                    wait(lambda q:q['position']>=s['duration']-3 or q['state']=='Ended',15)
                    wait(lambda s:s['state']=='Playing' and s['path']==songs[0]['path'] and s['position']<3 and s['bytes_written']>65536,15)
                else:
                    next_path=songs[1]['path'] if mode=='sequence' else None
                    wait(lambda s:s['state']=='Playing' and (s['path']==next_path if next_path else s['path']!=songs[0]['path']),15)
                report['checks'].append('real_eof_'+mode);save()
            f('Audiobook','TestSleepTimer');wait(lambda s:s['state']=='SleepEnded' and not s['active'],25)
            time.sleep(1.4);assert state()['state']=='SleepEnded';report['checks'].append('sleep_stops_repeat_mode')
            assert f('Audiobook','List')['tracks']==stories
            report.update(passed=True,song_count=20,story_count=len(stories),app_count=len(apps))
        finally:
            f('SystemCore','StopApp',{'AppId':app['app_id']});f('Audiobook','Stop')
            for path,data in saved.items():
                if data is not None:f('Storage','FSWriteText',{'Path':path,'Data':data})
                elif f('Storage','FSStat',{'Path':path})['exists']:f('Storage','FSRemove',{'Path':path})
            f('AudioPlayback','SetVolume',{'Volume':before['resume_volume']})
            f('DeviceModes','SetAutoDeepSleep',{'Minutes':before['auto_deep_sleep_minutes']})
            for path,data in saved.items():
                if data is not None:assert f('Storage','FSReadText',{'Path':path})==data
            assert f('DeviceModes','GetState')['resume_volume']==before['resume_volume']
            assert f('ChildMode','GetState')['configured']==child['configured']
            report['preferences_restored']=True;save()
    print('Verified songs, separate stories, native PCM, real EOF modes, sleep completion and preserved settings.',flush=True)

if __name__=='__main__':main()
