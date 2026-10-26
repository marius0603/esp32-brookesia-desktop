"""Check on-device digital inference/routing; physical child-voice QA is separate."""
import argparse,json,time
from pathlib import Path
from verify_child_mode import Client
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--resources-only',action='store_true',help='Check unrelated phrases, model reloads and microphone handoff; no claim about command accuracy')
    options=parser.parse_args()
    texts={1:'讲故事',2:'暂停故事',3:'还要听',4:'下一篇',5:'大声一点',6:'小声点',7:'我要睡觉了',8:'还剩几分钟'}
    report={'passed':False,'scope':'resources_only' if options.resources_only else 'full','acoustic_child_voice_test':False,'phrases':[],'short_phrase_limitations':['暂停','继续','继续播放','大声点','晚安','还有多久']}
    with Client('COM5',timeout=25) as c:
        # Keep the first panic line and register dump before cleanup RPCs can
        # obscure it. Private runtime logs must never be published.
        wire=(ROOT/'runtime/offline-voice-wire-private.log').open('wb',buffering=0)
        readline=c.serial.readline
        def capture(*args,**kwargs):
            line=readline(*args,**kwargs);wire.write(line);return line
        c.serial.readline=capture
        c.hello()
        def call(s,f,p=None):return c.call(s,f,p or {})['result']
        def until(predicate,seconds=30):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                value=predicate()
                if value:return value
                time.sleep(.2)
            raise TimeoutError('Offline check timed out')
        original=call('DeviceModes','GetState');volume=original['resume_volume']
        wifi_before=call('Wifi','GetGeneralState')
        try:
            call('DeviceModes','Wake')
            call('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
            call('VoiceAssistant','Disconnect')
            # Release paused diagnostic UIs before measuring the recognizer.
            # The shell stays running; parent policy and saved settings remain.
            for app in call('SystemCore','ListApps'):
                if app['manifest']['id'] in ('local.voiceassistant','local.flipclock') and app['state'] in ('Running','Paused','Starting'):
                    call('SystemCore','RequestCloseApp',{'AppId':app['app_id']})
            time.sleep(1)
            call('OfflineVoice','SetEnabled',{'Enabled':True})
            until(lambda:call('OfflineVoice','GetState')['active'])
            call('DeviceModes','SetQuietHours',{'Enabled':False,'StartMinute':original['quiet_start_minute'],'EndMinute':original['quiet_end_minute']})
            call('DeviceModes','SetDoNotDisturb',{'Enabled':False})
            call('AudioPlayback','SetVolume',{'Volume':30})
            # Actual radio stops while the USB control path remains available.
            call('Wifi','TriggerGeneralAction',{'Action':'Stop'});time.sleep(2)
            wifi=until(lambda:(v if (v:=call('Wifi','GetGeneralState'))=='Inited' else None))
            report['wifi_off']=wifi=='Inited'
            for command in ([] if options.resources_only else [1,2,3,4,6,5,8,7]):
                if command==8:
                    call('Audiobook','SetSleepTimer',{'Minutes':15});announcements=call('Audiobook','GetState')['announcement_count']
                # A missed utterance may be repeated once, just as in real use.
                # Every miss is retained; resource/routing errors fail immediately.
                trials=[]
                for attempt in (1,2):
                    before=call('OfflineVoice','GetState');count=before['recognized_count']
                    call('OfflineVoice','TestPhrase',{'Command':command})
                    try:
                        state=until(lambda:(v if (v:=call('OfflineVoice','GetState'))['recognized_count']>count else None),20)
                        assert state['last_command']==command and not state['error'],state
                        trials.append({'attempt':attempt,'recognized':True,'score':state['last_score']});break
                    except TimeoutError:
                        missed=call('OfflineVoice','GetState')
                        trials.append({'attempt':attempt,'recognized':False,'reason':missed['error'] or 'No matching command'})
                        report.setdefault('misses',[]).append({'command':command,'attempt':attempt,'reason':trials[-1]['reason']})
                        if missed['error'] or attempt==2:raise
                        print('Missed utterance; repeating once: '+str(command),flush=True);time.sleep(1)
                assert state['last_command']==command and not state['error'],state
                assert state['network_audio_upload'] is False
                until(lambda:not call('OfflineVoice','GetState')['diagnostic_in_progress']);time.sleep(3)
                book=call('Audiobook','GetState')
                released=until(lambda:(v if not (v:=call('OfflineVoice','GetState'))['command_model_loaded'] and not v['image_cache_limited'] else None),8)
                assert released['image_cache_limit_bytes']==1048576
                if command==1:assert book['active'] and book['path']
                if command==2:assert book['state']=='Paused'
                if command==3:assert book['state']=='Playing'
                if command==4:assert book['active']
                if command==6:assert call('AudioPlayback','GetVolume')==20
                if command==5:assert call('AudioPlayback','GetVolume')==30
                if command==8:
                    until(lambda:call('Audiobook','GetState')['announcement_count']>announcements)
                    assert call('Audiobook','GetState')['last_announcement']==15
                if command==7:
                    until(lambda:call('Audiobook','GetState')['sleep_completed'])
                    assert call('DeviceModes','GetState')['screen_asleep']
                report['phrases'].append({'command':command,'text':texts[command],'trials':trials,'score':state['last_score'],'internal_free':state['internal_free'],'psram_free':state['psram_free']})
                print('Digital phrase passed: '+str(command),flush=True)
            report['negative_phrases']=[]
            for fixture in (9,10,11):
                call('DeviceModes','Wake')
                before=call('OfflineVoice','GetState')
                call('OfflineVoice','TestPhrase',{'Command':fixture})
                time.sleep(1)
                until(lambda:not call('OfflineVoice','GetState')['diagnostic_in_progress'])
                until(lambda:not call('OfflineVoice','GetState')['listening'],20)
                after=until(lambda:(v if not (v:=call('OfflineVoice','GetState'))['command_model_loaded'] and not v['image_cache_limited'] else None),8)
                assert after['wake_count']>before['wake_count'],after
                assert after['recognized_count']==before['recognized_count'],after
                report['negative_phrases'].append(fixture)
                print('Unrelated phrase rejected: '+str(fixture),flush=True)
            # Multiple cycles catch model loader lifetime errors and leaked instances.
            samples=[]
            for _ in range(3):
                call('OfflineVoice','SetEnabled',{'Enabled':False})
                until(lambda:not call('OfflineVoice','GetState')['microphone_open'])
                call('OfflineVoice','SetEnabled',{'Enabled':True})
                state=until(lambda:(v if (v:=call('OfflineVoice','GetState'))['active'] else None))
                # Desktop images may repopulate ~333KB between idle samples.
                # Compare the same loaded phase, after production cache eviction,
                # rather than attributing an unrelated GUI cache to a model leak.
                call('OfflineVoice','ListenNow')
                state=until(lambda:(v if (v:=call('OfflineVoice','GetState'))['command_model_loaded'] else None))
                assert state['image_cache_limited'] and state['image_cache_limit_bytes']==0
                samples.append({'phase':'model_loaded_cache_disabled','internal':state['internal_free'],'psram':state['psram_free']})
                until(lambda:not (s:=call('OfflineVoice','GetState'))['command_model_loaded'] and not s['image_cache_limited'],20)
            assert max(s['psram'] for s in samples)-min(s['psram'] for s in samples)<100000,samples
            report['reloads']=samples
            # The existing assistant's local microphone test uses the same takeover
            # path as online chat, with no audio upload. Parent policy is preserved.
            child=call('ChildMode','GetState')
            if not child.get('enabled',False):
                call('VoiceAssistant','TestMicrophone')
                until(lambda:not call('OfflineVoice','GetState')['microphone_open'])
                assistant=until(lambda:(v if (v:=call('VoiceAssistant','GetState'))['state'] in ('Tested','Error') else None),20)
                assert assistant['state']=='Tested' and assistant['captured_frames']>=48000,assistant['error']
                until(lambda:call('OfflineVoice','GetState')['active'])
                report['assistant_microphone_handoff']=True
            else:report['assistant_microphone_handoff']='Skipped: parent policy retained'
            report['state']=call('OfflineVoice','GetState');assert report['state']['stack_free_min_bytes']>=2048
            assert report['state']['feed_stack_free_min_bytes']>=2048
            report['passed']=True
        except Exception as error:
            report['error']=str(error)
            c.serial.timeout=.2
            end=time.monotonic()+5
            while time.monotonic()<end:capture()
            c.serial.timeout=25
            raise
        finally:
            try:
                if wifi_before!='Inited':call('Wifi','TriggerGeneralAction',{'Action':'Start'})
            except Exception:pass
            for service,function,params in (
                ('Audiobook','Stop',{}),('DeviceModes','Wake',{}),
                ('AudioPlayback','SetVolume',{'Volume':volume}),
                ('DeviceModes','SetQuietHours',{'Enabled':original['quiet_hours_enabled'],'StartMinute':original['quiet_start_minute'],'EndMinute':original['quiet_end_minute']}),
                ('DeviceModes','SetDoNotDisturb',{'Enabled':original['manual_do_not_disturb']}),
                ('DeviceModes','SetAutoDeepSleep',{'Minutes':original['auto_deep_sleep_minutes']})):
                try:call(service,function,params)
                except Exception as cleanup_error:
                    report.setdefault('cleanup_errors',[]).append(str(cleanup_error))
            filename='offline-voice-resources-verification.json' if options.resources_only else 'offline-voice-verification.json'
            (ROOT/'runtime'/filename).write_text(json.dumps(report,indent=2))
            c.serial.readline=readline
            wire.close()
    print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
