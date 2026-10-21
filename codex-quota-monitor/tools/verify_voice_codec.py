"""Run on-device Opus regression without capturing, uploading, or playing real audio."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from quota_monitor.brookesia import StableUsbClient

parser=argparse.ArgumentParser()
parser.add_argument('--port',default='COM5')
parser.add_argument('--output',type=Path,default=ROOT/'runtime/assistant-codec-check.json')
args=parser.parse_args()
with StableUsbClient(args.port,timeout=25) as client:
    client.hello()
    baseline=client.call('VoiceAssistant','GetState',{})['result']
    client.call('VoiceAssistant','Disconnect',{})
    for _ in range(80):
        state=client.call('VoiceAssistant','GetState',{})['result']
        if not state['active']:break
        time.sleep(.25)
    assert not state['active'],'Previous session is still stopping'
    assert state['captured_frames']==baseline['captured_frames'],'Disconnect unexpectedly captured audio'
    for name in ('StartListening','StopListening','Interrupt'):
        try:
            client.call('VoiceAssistant',name,{})
        except RuntimeError:
            pass
        else:
            raise AssertionError(f'{name} must reject when disconnected')
    runs=[]
    for run in range(2):
        client.call('VoiceAssistant','TestCodec',{})
        for _ in range(120):
            state=client.call('VoiceAssistant','GetState',{})['result']
            if not state['active']:break
            time.sleep(.25)
        print(json.dumps(state,ensure_ascii=True),flush=True)
        assert state['state']=='Tested' and not state['error'],state
        assert state['codec_test_frames']==120,state
        assert state['captured_frames']==state['sent_packets']==state['played_bytes']==0,state
        assert state['stack_limit_bytes']==40*1024 and state['stack_total_bytes']==48*1024,state
        assert state['control_stack_total_bytes']==16*1024 and state['control_stack_free_min_bytes']>1024,state
        assert 0<state['stack_peak_used_bytes']<state['stack_limit_bytes'],state
        runs.append(state)
        time.sleep(.1)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'passes':2,'runs':runs},ensure_ascii=False,indent=2),encoding='utf-8')
