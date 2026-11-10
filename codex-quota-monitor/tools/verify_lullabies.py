"""Verify the SD lullaby collection, ten decodes, real collection EOF and fade-out."""
import argparse
import json
from pathlib import Path
import time
from deploy_clock_widgets import tree_hash
from deploy_lullabies import package
from maintenance_client import SharedPowerDiagnosticClient

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='COM5')
    args=parser.parse_args()
    manifest=json.loads((ROOT/'samples/songs/lullabies-20261109.json').read_text(encoding='utf-8'))
    previous=json.loads((ROOT/'codex-quota-monitor/runtime/lullabies-before.json').read_text(encoding='utf-8'))
    report={'passed':False,'decodes':[],'checks':[]}
    output=ROOT/'codex-quota-monitor/runtime/lullabies-verification.json'
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with SharedPowerDiagnosticClient(args.port,timeout=35) as client:
        client.hello()
        def call(service,name,params=None):return client.call_timeout(service,name,params or {})['result']
        def state():return call('Audiobook','GetState')
        def wait(predicate,seconds=22):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                value=state();assert not value['error'],value
                if predicate(value):return value
                time.sleep(.25)
            raise AssertionError('Playback deadline: '+str(value))
        end=time.monotonic()+90
        while True:
            apps=call('SystemCore','ListApps')
            app=next((a for a in apps if a['manifest']['id']=='local.nurserysongs'),None)
            if app and app['manifest']['version']=='0.1.3':break
            assert time.monotonic()<end,'New app was not registered after restart'
            time.sleep(1)
        modes=call('DeviceModes','GetState');book=state();child=call('ChildMode','GetState')
        assert not child['enabled'],'Do not bypass parent policy during testing'
        for service in ('Audiobook','Radio','VoiceAssistant','LocalVoice'):
            assert not call(service,'GetState')['active'],'Finish active audio before verification'
        assert modes['firmware_version']==previous['states']['DeviceModes']['firmware_version']
        # A parent may adjust volume between deployment and verification.
        # Preserve the current value below rather than enforcing an old snapshot.
        assert {a['manifest']['id']:a['manifest']['version'] for a in apps if a['manifest']['id']!='local.nurserysongs'}=={
            a['manifest']['id']:json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps'].get(a['manifest']['id'],a['manifest']['version']) for a in previous['apps'] if a['manifest']['id']!='local.nurserysongs'}
        stories=call('Audiobook','List')['tracks'];songs=call('Audiobook','ListSongs')['tracks']
        assert stories==previous['stories'] and len(stories)==30
        lullabies=[t for t in songs if t['path'].startswith(manifest['device_root']+'/')]
        nursery=[t for t in songs if t not in lullabies]
        assert len(lullabies)==10 and nursery==previous['songs'] and len(nursery)==20
        assert {t['title'] for t in lullabies}=={t['title'] for t in manifest['songs']}
        assert not {t['path'] for t in songs}&{t['path'] for t in stories}
        for folder in ('app','res'):
            files={n[len(folder)+1:]:d for n,d in package('0.1.3').items() if n.startswith(folder+'/')}
            assert call('SdResources','InspectTree',{'Path':'/sdcard/apps/local.nurserysongs/'+folder})['sha256']==tree_hash(files)
        report['checks'].append('source_tree_and_separate_20_plus_10_catalog')
        call('SystemCore','StopApp',{'AppId':app['app_id']})
        saved={}
        for path in ('/sdcard/apps/local.nurserysongs/data/player.json','/sdcard/apps/local.nurserysongs/data/play-mode.json',
                     '/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json'):
            saved[path]=call('Storage','FSReadText',{'Path':path}) if call('Storage','FSStat',{'Path':path})['exists'] else None
        def start():
            call('SystemCore','StartApp',{'AppId':app['app_id']});time.sleep(1.2)
            active=call('SystemCore','GetActiveApp')
            assert active['app_id']==app['app_id'] and active['state']=='Running' and not active['last_error'],active
        def play(track):
            call('Audiobook','Play',{'Path':track['path'],'Position':0})
            return wait(lambda v:v['state']=='Playing' and v['path']==track['path'] and v['bytes_written']>=65536)
        try:
            call('DeviceModes','Wake');call('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
            call('AudioPlayback','SetVolume',{'Volume':0})
            start();assert not state()['active'];report['checks'].append('silent_collection_home')
            for track in lullabies:
                value=play(track)
                duration=next(s['duration_seconds'] for s in manifest['songs'] if s['title']==track['title'])
                assert abs(value['duration']-duration)<2
                report['decodes'].append({'title':track['title'],'duration':value['duration'],'bytes_written':value['bytes_written']});save()
                call('Audiobook','Stop');print('Decoded '+track['title'],flush=True)
            play(lullabies[0]);first=state()['bytes_written'];begin=time.monotonic();time.sleep(20);value=state();elapsed=time.monotonic()-begin
            assert value['state']=='Playing' and not value['error'] and value['pcm_starvations']==0,value
            assert value['bytes_written']-first>elapsed*16000*4*.90 and value['write_gap_max_us']<100000,value
            report['continuity']={k:value[k] for k in ('pcm_starvations','write_gap_max_us','decode_max_us','pcm_stack_free_min_bytes')}
            report['checks'].append('20_second_continuous_pcm')
            call('Audiobook','SetSongMode',{'Mode':'sequence'})
            value=play(lullabies[0]);time.sleep(1.3)
            call('Audiobook','Seek',{'Seconds':value['duration']-1})
            wait(lambda v:v['state']=='Playing' and v['path']==lullabies[1]['path'])
            report['checks'].append('real_lullaby_eof_stays_in_collection')
            value=play(lullabies[-1]);time.sleep(1.3)
            call('Audiobook','Seek',{'Seconds':value['duration']-1});wait(lambda v:v['state']=='Ended' and not v['active'])
            time.sleep(1.5);assert state()['state']=='Ended' and state()['path']==lullabies[-1]['path']
            report['checks'].append('last_lullaby_does_not_cross_to_nursery')
            call('Audiobook','SetSongMode',{'Mode':'repeat_one'});value=play(lullabies[0]);time.sleep(1.3)
            call('Audiobook','Seek',{'Seconds':value['duration']-1})
            wait(lambda v:v['position']>=value['duration']-3 or v['state']=='Ended')
            wait(lambda v:v['state']=='Playing' and v['path']==lullabies[0]['path'] and v['position']<3)
            report['checks'].append('real_lullaby_single_repeat')
            call('Audiobook','TestSleepTimer');wait(lambda v:v['state']=='SleepEnded' and not v['active'],25)
            time.sleep(1.5);assert state()['state']=='SleepEnded'
            report['checks'].append('fade_goodnight_stops_repeat')
            call('Audiobook','SetSongMode',{'Mode':'sequence'});value=play(nursery[0]);time.sleep(1.3)
            call('Audiobook','Seek',{'Seconds':value['duration']-1})
            wait(lambda v:v['state']=='Playing' and v['path']==nursery[1]['path'])
            report['checks'].append('original_nursery_eof_still_separate')
            report.update(passed=True,app_version='0.1.3',firmware=modes['firmware_version'],app_count=len(apps),story_count=30,nursery_count=20,lullaby_count=10)
        finally:
            call('SystemCore','StopApp',{'AppId':app['app_id']});call('Audiobook','Stop')
            call('Audiobook','SetSongMode',{'Mode':book['song_play_mode']})
            for path,data in saved.items():
                if data is not None:call('Storage','FSWriteText',{'Path':path,'Data':data})
                elif call('Storage','FSStat',{'Path':path})['exists']:call('Storage','FSRemove',{'Path':path})
            call('AudioPlayback','SetVolume',{'Volume':modes['resume_volume']})
            call('DeviceModes','SetAutoDeepSleep',{'Minutes':modes['auto_deep_sleep_minutes']})
            assert call('Audiobook','List')['tracks']==stories
            assert call('DeviceModes','GetState')['resume_volume']==modes['resume_volume']
            for path,data in saved.items():
                if data is not None:assert call('Storage','FSReadText',{'Path':path})==data
            report['preferences_restored']=True;save()
            if report['passed']:start()
    print('Ten lullabies, separate collection EOF, PCM continuity and sleep fade verified.',flush=True)


if __name__=='__main__':main()
