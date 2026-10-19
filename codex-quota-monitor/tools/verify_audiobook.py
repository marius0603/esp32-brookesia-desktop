"""Verify the no-card player, retained-context opens and locally generated speaker tone."""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from quota_monitor.brookesia import StableUsbClient

report={}
with StableUsbClient('COM5',timeout=25) as client:
    client.hello()
    apps=client.call('SystemCore','ListApps',{})['result']
    app=next(a for a in apps if a['manifest']['id']=='local.audiobook')
    report['preserved_apps']=[{'id':a['manifest']['id'],'version':a['manifest']['version']} for a in apps]
    for _ in range(2):
        client.call('SystemCore','StopApp',{'AppId':app['app_id']})
        client.call('SystemCore','StartApp',{'AppId':app['app_id']})
        active=client.call('SystemCore','GetActiveApp',{})['result']
        assert active['app_id']==app['app_id'] and active['state']=='Running' and not active['last_error']
    report['reopens']=2
    report['library']=client.call('Audiobook','List',{})['result']
    original_volume=client.call('AudioPlayback','GetVolume',{})['result']
    try:
        client.call('AudioPlayback','SetVolume',{'Volume':20})
        client.call('Audiobook','TestTone',{})
        print('Playing a two second, low-amplitude locally generated tone.',flush=True)
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            state=client.call('Audiobook','GetState',{})['result']
            if not state['active'] and state['state'] in ('Ended','Error'):break
            time.sleep(.25)
        report['tone']=state
        assert state['state']=='Ended' and state['bytes_written']==64000 and not state['error'],state
        try:
            client.call('Audiobook','Play',{'Path':'/sdcard/audiobooks/absent.mp3','Position':0})
        except RuntimeError as exc:
            assert 'missing' in str(exc)
            report['missing_file_rejected']=True
        else:
            raise AssertionError('Missing file was accepted')
    finally:
        client.call('AudioPlayback','SetVolume',{'Volume':original_volume})
    report['volume_restored']=client.call('AudioPlayback','GetVolume',{})['result']==original_volume
    report['active']=client.call('SystemCore','GetActiveApp',{})['result']
(ROOT/'runtime/audiobook-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True),flush=True)
