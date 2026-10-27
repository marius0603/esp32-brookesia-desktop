"""Verify the real cloud/TTS downlink silently, preserving volume preferences."""
import argparse,datetime,json,time
from pathlib import Path
from deploy_audiobook_sleep import StoryClient

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--port',required=True);a=p.parse_args()
    output=ROOT/'runtime/pc-voice-downlink-verification.json'
    report={'passed':False,'started':datetime.datetime.now().isoformat(timespec='seconds')}
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    with StoryClient(a.port,timeout=25) as c:
        c.hello()
        def call(s,f,args=None):return c.call(s,f,args or {})['result']
        original=call('DeviceModes','GetState');before=call('LocalVoice','GetState')
        assert before['channel'] and before['endpoint'].startswith('wss://')
        state=before
        try:
            call('AudioPlayback','SetVolume',{'Volume':0})
            call('LocalVoice','TestReply')
            deadline=time.monotonic()+120
            while True:
                state=call('LocalVoice','GetState')
                if state['state']=='Error' or state['error'] or not state['active']:
                    raise RuntimeError(state['error'] or state['message'])
                if state['played_bytes']>before['played_bytes'] and state['state']=='Ready':break
                if time.monotonic()>deadline:raise TimeoutError('No completed device playback')
                time.sleep(.3)
            assert '连接成功' in state['answer'] and state['captured_frames']==before['captured_frames']
            assert state['turn']==before['turn']+1,'Connection restarted during playback'
            assert state['max_playback_gap_ms']<250,('Audio writer stalled',state['max_playback_gap_ms'])
            report.update(passed=True,public_wss=True,cloud_tts_device_playback=True,microphone_not_opened=True)
        except Exception as error:
            report['error']=str(error);raise
        finally:
            report.update(before=before,after=state)
            try:
                call('AudioPlayback','SetVolume',{'Volume':original['resume_volume']})
                report['volume_restored']=call('DeviceModes','GetState')['resume_volume']
            finally:output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Real public cloud/TTS playback verified:',state['played_bytes']-before['played_bytes'],
            'PCM bytes; maximum write gap',state['max_playback_gap_ms'],'ms; volume restored.')
if __name__=='__main__':main()
