"""Verify scheduled speaker mute and visible native weather layers on COM5."""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verify_child_mode import Client

def main():
    report={}
    with Client('COM5',timeout=25) as c:
        c.hello()
        def call(s,f,p=None):return c.call(s,f,p or {})['result']
        def state():return call('DeviceModes','GetState')
        def wait(test,timeout=15):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                result=test()
                if result:return result
                time.sleep(.3)
            raise RuntimeError('Condition timed out')
        original=state();volume=original['resume_volume'] if original['do_not_disturb'] else call('AudioPlayback','GetVolume')
        def quiet(on,start,end):
            call('DeviceModes','SetQuietHours',{'Enabled':on,'StartMinute':start,'EndMinute':end})
            wait(lambda:not state()['pending_save'] and not state()['audio_pending'])
        try:
            call('DeviceModes','Wake');call('DeviceModes','SetDoNotDisturb',{'Enabled':False});quiet(False,1320,420)
            call('AudioPlayback','SetVolume',{'Volume':18})
            apps=call('SystemCore','ListApps');weather=next(a for a in apps if a['manifest']['id']=='local.weather')
            assert weather['manifest']['version']=='0.2.5'
            call('SystemCore','RequestCloseApp',{'AppId':weather['app_id']});time.sleep(.7)
            call('SystemCore','StartApp',{'AppId':weather['app_id']})
            wait(lambda:(a:=call('SystemCore','GetActiveApp')).get('app_id')==weather['app_id'] and a.get('state')=='Running')
            time.sleep(3)
            layers=call('DeviceModes','GetWeatherLayers')['layers'];report['weather_layers']=layers
            shade=next(n for n in layers if n['kind']=='shade')
            assert shade['opacity']==45 and shade['effective_opacity']==45,shade
            assert not any(n['order']>shade['order'] and n['width']>=480 and n['height']>=480 and n['effective_opacity']==255 and n['background_opacity']==255 for n in layers),layers
            effects=[n for n in layers if n['kind'] in ('moon','sun','cloud')]
            assert all(n['effective_opacity']>0 for n in effects),layers
            # The moon is now a PNG with per-pixel alpha rather than a colored surface.
            report['weather_state']=json.loads(call('Storage','FSReadText',{'Path':'/littlefs/weather-state.json'}))
            assert report['weather_state']['fx_active'] and not report['weather_state']['fx_error']
            print('Actual LVGL shade opacity is 45; weather effects visible and no later opaque full-screen surface',flush=True)
            minute=state()['local_minute'];assert minute>=0
            # This interval wraps midnight and covers the current evening.
            start=(minute-10)%1440;end=(minute-20)%1440
            quiet(True,start,end);assert state()['do_not_disturb'] and call('AudioPlayback','GetVolume')==0
            call('AudioPlayback','SetVolume',{'Volume':27});assert state()['resume_volume']==18
            report['wrapping_interval']=state()
            quiet(False,start,end);assert call('AudioPlayback','GetVolume')==18
            # Outside a short interval later today: speaker stays at prior volume.
            quiet(True,(minute+10)%1440,(minute+20)%1440);assert not state()['do_not_disturb']
            quiet(True,0,0);assert state()['do_not_disturb'];report['all_day']=state()
            try:
                quiet(True,-1,420)
            except RuntimeError as exc:
                assert 'whole minutes' in str(exc),str(exc)
            else:raise AssertionError('Invalid minute accepted')
            # Verify an actual clock boundary without changing system time.
            minute=state()['local_minute'];end=(minute+2)%1440
            quiet(True,(minute-1)%1440,end);assert state()['do_not_disturb']
            report['before_boundary']=state();started=time.monotonic();last=-1
            while time.monotonic()-started<135:
                current=state()
                if not current['do_not_disturb']:
                    assert current['local_minute']==end,current
                    wait(lambda:not state()['audio_pending'])
                    assert call('AudioPlayback','GetVolume')==18
                    report['after_boundary']=state();report['boundary_wait_seconds']=time.monotonic()-started
                    break
                elapsed=int(time.monotonic()-started)//20
                if elapsed!=last:print('Waiting for real quiet-hours end boundary',flush=True);last=elapsed
                time.sleep(.5)
            else:raise RuntimeError('Scheduled mute did not stop at end time')
            print('Scheduled mute automatically ended and restored volume at the real minute boundary',flush=True)
        finally:
            quiet(False,1320,420);call('DeviceModes','SetDoNotDisturb',{'Enabled':False})
            wait(lambda:not state()['audio_pending']);call('AudioPlayback','SetVolume',{'Volume':volume})
            call('DeviceModes','SetDoNotDisturb',{'Enabled':False});wait(lambda:not state()['pending_save'])
            report['final']=state();report['memory']=call('Utils','GetMemorySnapshot')
            (ROOT/'runtime/quiet-hours-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
