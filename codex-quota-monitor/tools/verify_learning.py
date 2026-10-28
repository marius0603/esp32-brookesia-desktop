"""Verify the installed offline app; microphone exercise is opt-in and volatile."""
import argparse
import json
from pathlib import Path
import time
import wave
from deploy_audiobook_sleep import StoryClient

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',required=True)
    parser.add_argument('--before',type=Path,help='Private pre-install snapshot for preservation checks')
    parser.add_argument('--record-test',action='store_true',help='Record one second in device memory, silently replay, then erase')
    args=parser.parse_args()
    report={'passed':False,'physical_swipe_verified':False,'physical_listening_verified':False,'record_test':args.record_test}
    with StoryClient(args.port,timeout=30) as client:
        original_readline=client.serial.readline
        def diagnostic_readline(*a,**kw):
            line=original_readline(*a,**kw)
            with (ROOT/'runtime/learning-usb-check.log').open('ab') as log:log.write(line)
            return line
        client.serial.readline=diagnostic_readline
        client.hello()
        def call(service,name,params=None):return client.call(service,name,params or {})['result']
        def wait_audio():
            deadline=time.monotonic()+24
            while True:
                state=call('LearningAudio','GetState')
                if not state['active']:
                    assert not state['error'],state
                    return state
                assert time.monotonic()<deadline,'Learning audio did not finish'
                time.sleep(.1)
        apps=call('SystemCore','ListApps')
        report['app_list_bytes']=len(json.dumps(apps,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
        app=next(a for a in apps if a['manifest']['id']=='local.lightlearning')
        assert app['manifest']['version']==json.loads((REPO/'versions.json').read_text(encoding='utf-8'))['apps']['local.lightlearning']
        assert next(a for a in apps if a['manifest']['id']=='local.childmode')['manifest']['version']=='0.1.1'
        modes=call('DeviceModes','GetState')
        expected=json.loads((REPO/'versions.json').read_text(encoding='utf-8'))['firmware']
        assert modes['firmware_version']==expected and not modes['screen_locked']
        child=call('ChildMode','GetState')
        assert not child['enabled'] or (child['allow_learning'] and not child['resting']),'Parent authorization required'
        volume=call('AudioPlayback','GetVolume')
        tracks=call('Audiobook','List')['tracks']
        if args.before:
            before=json.loads(args.before.read_text(encoding='utf-8'))
            assert tracks==before['tracks'] and volume==before['volume']
            for key in ('configured','enabled','allow_audiobook','allow_weather','allow_clock','allow_assistant','max_volume','daily_minutes','night_enabled','night_start','night_end'):
                assert child[key]==before['child'][key],key
            for path in ('/littlefs/audiobook-bookmark.json','/littlefs/voice-assistant-backend.json'):
                assert call('Storage','FSReadText',{'Path':path})==before[path],path
            report['preexisting_data_preserved']=True
        fonts=json.loads(call('Storage','FSReadText',{'Path':'/littlefs/system/fonts/index.json'}))
        font=next(f for f in fonts['fonts'] if f['id']=='learning')
        assert font['languages']==['en','zh_CN']
        report['fonts_registered']=True
        call('DeviceModes','Wake')
        call('SystemCore','StartApp',{'AppId':app['app_id']})
        time.sleep(1)
        try:
            call('AudioPlayback','SetVolume',{'Volume':0})
            report['samples']=[]
            pack=json.loads((REPO/'brookesia-apps/light-learning/packs/starter/pack.json').read_text(encoding='utf-8'))
            for item in pack['cards']+[pack['english'][0]]:
                local=REPO/'brookesia-apps/light-learning/packs/starter'/item['audio']
                with wave.open(str(local),'rb') as source:expected=source.getnframes()*2
                call('LearningAudio','PlayFile',{'Path':'/sdcard/learning/packs/starter/'+item['audio']})
                state=wait_audio()
                assert state['played_bytes']==expected,state
                assert state['stack_free_min_bytes']>=1024,state
                report['samples'].append({'audio':item['audio'],'played_bytes':expected,'stack_free_min_bytes':state['stack_free_min_bytes']})
            if args.record_test:
                call('LearningAudio','StartRecording',{'Seconds':1})
                state=wait_audio()
                assert state['state']=='Recorded' and 30000<=state['recorded_bytes']<=32000,state
                report['recording']={'recorded_bytes':state['recorded_bytes'],'recorded_ms':state['recorded_ms'],'stack_free_min_bytes':state['stack_free_min_bytes']}
                call('LearningAudio','Replay')
                state=wait_audio()
                assert state['played_bytes']==state['recorded_bytes'] and state['recorded_bytes']>0,state
                report['volatile_replay_passed']=True
            call('LearningAudio','Discard')
            assert wait_audio()['recorded_bytes']==0
            report['recording_erased']=True
        finally:
            call('LearningAudio','Discard')
            call('AudioPlayback','SetVolume',{'Volume':volume})
        report['active_app']=call('SystemCore','GetActiveApp')
        assert report['active_app']['manifest']['id']=='local.lightlearning' and report['active_app']['state']=='Running' and not report['active_app']['last_error'],report['active_app']
        assert call('Audiobook','List')['tracks']==tracks and call('AudioPlayback','GetVolume')==volume
        report['stories']=len(tracks)
        report['volume_restored']=volume
        report['passed']=True
    (ROOT/'runtime/learning-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Learning app, full WAV playback and data preservation passed; recording test:',args.record_test)

if __name__=='__main__':main()
