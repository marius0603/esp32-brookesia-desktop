"""Open the installed clock twice and compare actual device time and flap progress."""
import argparse
import datetime
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from deploy_audiobook_sleep import StoryClient

report={}
parser=argparse.ArgumentParser()
parser.add_argument('--port',default='COM3')
args=parser.parse_args()
with StoryClient(args.port,timeout=30) as c:
    c.hello()
    ready_until=time.monotonic()+60
    while True:
        apps=c.call('SystemCore','ListApps',{})['result']
        shell=next((a for a in apps if a['manifest']['id']=='brookesia.system.super.shell'),None)
        if shell and shell['state']=='Running' and any(a['manifest']['id']=='local.lightlearning' for a in apps):break
        assert time.monotonic()<ready_until,'Desktop did not finish startup'
        time.sleep(1)
    app=next(a for a in apps if a['manifest']['id']=='local.flipclock')
    assert app['manifest']['version']=='0.1.1'
    for _ in range(2):
        c.call('SystemCore','StopApp',{'AppId':app['app_id']})
        c.call('SystemCore','StartApp',{'AppId':app['app_id']})
        active=c.call('SystemCore','GetActiveApp',{})['result']
        assert active['app_id']==app['app_id'] and active['state']=='Running' and not active['last_error']
    # Reproduce the stale Running state: another app takes the foreground,
    # then closes. Starting the already-running clock must show it again.
    other=next(a for a in apps if a['manifest']['id']=='local.lightlearning')
    c.call('SystemCore','StartApp',{'AppId':other['app_id']})
    c.call('SystemCore','StopApp',{'AppId':other['app_id']})
    c.call('SystemCore','StartApp',{'AppId':app['app_id']})
    active=c.call('SystemCore','GetActiveApp',{})['result']
    assert active.get('app_id')==app['app_id'] and active['state']=='Running' and not active['last_error'],active
    deadline=time.monotonic()+70
    while time.monotonic()<deadline:
        state=json.loads(c.call('Storage','FSReadText',{'Path':'/littlefs/clock-state.json'})['result'])
        if state['frames']>=4 and abs(time.time()-state['time']/1000)<15:break
        time.sleep(.25)
    expected=datetime.datetime.fromtimestamp(state['time']/1000,datetime.timezone(datetime.timedelta(hours=8))).strftime('%H%M')
    assert state['digits']==expected and state['frames']>=4 and not state['paused'],state
    assert abs(time.time()-state['time']/1000)<15
    report={'reopens':2,'stale_running_recovered':True,'device_time_matches':True,'state':state,'active':active}
(ROOT/'runtime/flip-clock-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Clock reopens, real Beijing time and half-flap updates verified',flush=True)
print(json.dumps(state),flush=True)
