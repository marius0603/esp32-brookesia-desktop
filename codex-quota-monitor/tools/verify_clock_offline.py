"""Hold an offline command window across a real clock minute flip; no upload."""
import json,time,datetime
from pathlib import Path
from verify_child_mode import Client as BaseClient
class Client(BaseClient):
    def read_json(self):
        while True:
            try:return super().read_json()
            except RuntimeError as error:
                text=str(error)
                if ('invalid device response:' in text and 'HalIface: : - [CustomDisplay] ' in text
                    and 'reference count ' in text.lower()):
                    self.diagnostic_lines.append(text.encode());continue
                raise
ROOT=Path(__file__).resolve().parents[1]
report={'passed':False}
with Client('COM5',timeout=25) as c:
    c.hello()
    def call(s,f,p=None):return c.call(s,f,p or {})['result']
    def clock():return json.loads(call('Storage','FSReadText',{'Path':'/littlefs/clock-state.json'}))
    call('VoiceAssistant','Disconnect');call('DeviceModes','Wake')
    app=next(a for a in call('SystemCore','ListApps') if a['manifest']['id']=='local.flipclock')
    if app['state'] in ('Running','Paused','Starting'):
        call('SystemCore','RequestCloseApp',{'AppId':app['app_id']});time.sleep(1)
    # Start at second 54 so model initialization and its 10 s detection window
    # cover the minute transition, when clock images need to redraw.
    # The clock records only its first flip per launch; start a fresh instance
    # just before the boundary rather than comparing an older diagnostic file.
    while not 52<=time.time()%60<53:time.sleep(.2)
    call('SystemCore','StartApp',{'AppId':app['app_id']});time.sleep(1)
    before=clock();initial=call('OfflineVoice','GetState')
    assert initial['active'] and not initial['listening'],initial['error']
    call('OfflineVoice','ListenNow');saw_loaded=False;lowest=2**32-1
    deadline=time.monotonic()+17
    while time.monotonic()<deadline:
        state=call('OfflineVoice','GetState')
        if state['command_model_loaded']:
            saw_loaded=True;lowest=min(lowest,state['psram_free'])
            assert state['image_cache_limited'] and state['image_cache_limit_bytes']==0
        elif saw_loaded and not state['image_cache_limited']:break
        if state['error']:raise RuntimeError(state['error'])
        time.sleep(.2)
    after=clock()
    assert saw_loaded and not state['command_model_loaded'] and not state['image_cache_limited'],state
    assert after['digits']!=before['digits'] and after['frames']>before['frames'],(before,after)
    expected=datetime.datetime.fromtimestamp(after['time']/1000,datetime.timezone(datetime.timedelta(hours=8))).strftime('%H%M')
    assert after['digits']==expected and lowest>=50000
    assert call('SystemCore','GetActiveApp')['app_id']==app['app_id']
    report.update(passed=True,digits=after['digits'],frames=after['frames'],psram_min=lowest,cache_restored=state['image_cache_limit_bytes'],reclaimed=state['cache_reclaimed_bytes'])
(ROOT/'runtime/clock-offline-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
