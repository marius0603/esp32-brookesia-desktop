"""Verify volume through the assistant's PCM writer, optionally with real keys.

Synthetic audio only: this check never opens the microphone or uploads audio.
Temporary loudness/quiet preferences are restored after diagnostics.
"""
import argparse,json,time
from pathlib import Path
from verify_child_mode import Client
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--physical',action='store_true');a=p.parse_args()
    report={'passed':False,'physical':a.physical,'samples':[]}
    with Client('COM5',timeout=25) as c:
        c.hello()
        def call(s,f,p=None):return c.call(s,f,p or {})['result']
        def until(test,seconds=15):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                v=test()
                if v:return v
                time.sleep(.1)
            raise TimeoutError('Assistant audio check timed out')
        original=call('DeviceModes','GetState')
        try:
            call('DeviceModes','Wake');call('VoiceAssistant','Disconnect')
            until(lambda:not call('VoiceAssistant','GetState')['active'])
            app=next(v for v in call('SystemCore','ListApps') if v['manifest']['id']=='local.voiceassistant')
            assert app['manifest']['version']=='0.1.1'
            if app['state'] not in ('Running','Paused'):call('SystemCore','StartApp',{'AppId':app['app_id']})
            time.sleep(.5);call('VoiceAssistant','Disconnect');until(lambda:not call('VoiceAssistant','GetState')['active'])
            call('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
            call('DeviceModes','SetQuietHours',{'Enabled':False,'StartMinute':original['quiet_start_minute'],'EndMinute':original['quiet_end_minute']})
            call('DeviceModes','SetDoNotDisturb',{'Enabled':False});call('AudioPlayback','SetVolume',{'Volume':30})
            start=call('DeviceModes','GetState');call('VoiceAssistant','TestSpeaker')
            until(lambda:call('VoiceAssistant','GetState')['played_bytes']>0)
            if a.physical:
                print('Assistant tone playing: press both physical volume keys now.',flush=True)
                end=time.monotonic()+33;last=-1
                while time.monotonic()<end:
                    state=call('VoiceAssistant','GetState');modes=call('DeviceModes','GetState')
                    if modes['volume_key_presses']!=last:
                        last=modes['volume_key_presses'];sample=call('DeviceModes','GetSpeakerVolume')
                        sample.update(presses=last,applied=modes['volume_key_applied'],target=modes['resume_volume'],gpio=modes['volume_key_last_gpio'])
                        report['samples'].append(sample);print(json.dumps(sample),flush=True)
                    if not state['active']:break
                    time.sleep(.2)
                assert modes['volume_key_applied']>start['volume_key_applied'],report['samples']
                assert len({v['codec_volume'] for v in report['samples'] if v['codec_open']})>1,report['samples']
            else:
                for volume in (10,30,0):
                    call('AudioPlayback','SetVolume',{'Volume':volume});time.sleep(.15)
                    sample=call('DeviceModes','GetSpeakerVolume');report['samples'].append(sample)
                    assert sample['codec_open'] and sample['codec_volume']==volume,sample
                    assert sample['mute_valid'] and sample['muted']==(volume==0),sample
                assert report['samples'][0]['dac_volume_register']<report['samples'][1]['dac_volume_register']
            state=call('VoiceAssistant','GetState')
            assert not state['error'] and state['captured_frames']==0 and state['sent_packets']==0
            report['no_microphone_or_upload']=True;report['passed']=True
        finally:
            call('VoiceAssistant','Disconnect');until(lambda:not call('VoiceAssistant','GetState')['active'])
            call('AudioPlayback','SetVolume',{'Volume':original['resume_volume']})
            call('DeviceModes','SetQuietHours',{'Enabled':original['quiet_hours_enabled'],'StartMinute':original['quiet_start_minute'],'EndMinute':original['quiet_end_minute']})
            call('DeviceModes','SetDoNotDisturb',{'Enabled':original['manual_do_not_disturb']})
            call('DeviceModes','SetAutoDeepSleep',{'Minutes':original['auto_deep_sleep_minutes']})
            name='assistant-physical-volume-verification.json' if a.physical else 'assistant-writer-volume-verification.json'
            (ROOT/'runtime'/name).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'physical':a.physical,'samples':report['samples']}),flush=True)
if __name__=='__main__':main()
