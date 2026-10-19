"""Exercise stop/start in retained JS contexts, then verify Pac-Man data and animation."""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from quota_monitor.brookesia import StableUsbClient

report={'opens':[]}
with StableUsbClient('COM5',timeout=40) as client:
    client.hello()
    apps=client.call('SystemCore','ListApps',{})['result']
    ids={a['manifest']['id']:a['app_id'] for a in apps}
    targets=('local.codex.quota','local.weather')
    for name in targets:
        client.call('SystemCore','StopApp',{'AppId':ids[name]})
    for index in range(12):
        name=targets[index%2]
        started=time.monotonic()
        try:
            client.call('SystemCore','StartApp',{'AppId':ids[name]})
            active=client.call('SystemCore','GetActiveApp',{})['result']
            assert active['app_id']==ids[name] and active['state']=='Running' and not active['last_error'],active
            result={'app':name,'ok':True,'seconds':round(time.monotonic()-started,3)}
        except Exception as exc:
            result={'app':name,'ok':False,'error':str(exc)}
        report['opens'].append(result)
        print(json.dumps(result),flush=True)
        client.call('SystemCore','StopApp',{'AppId':ids[name]})
    packet=json.loads((ROOT/'runtime/latest.json').read_text(encoding='utf-8'))
    assert packet['status']=='ok' and time.time()-packet['sampled_at']<180
    packet['bridge_at']=int(time.time())
    client.call('Storage','FSWriteText',{'Path':'/littlefs/quota.json','Data':json.dumps(packet,ensure_ascii=False)})
    client.call('SystemCore','StartApp',{'AppId':ids['local.codex.quota']})
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        value=json.loads(client.call('Storage','FSReadText',{'Path':'/littlefs/quota-ui-state.json'})['result'])
        if value['sampled_at']==packet['sampled_at'] and value.get('animation_frames',0)>=8:
            break
        time.sleep(0.5)
    report['pacman']=value
    assert value['sampled_at']==packet['sampled_at'] and value['animation_frames']>=8 and not value['stale']
    for window,key in zip(packet['windows'],('primary_remaining','secondary_remaining')):
        assert value[key]==100-window['used']
    report['apps']=client.call('SystemCore','ListApps',{})['result']
(ROOT/'runtime/runtime-reopen-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert all(result['ok'] for result in report['opens'])
print('12 repeated opens passed; real quota percentages and animation verified')
