"""Verify screen modes on the real board; --idle-test waits the full 10 minutes.

Does not read or alter the parent PIN. Restores the original playback volume.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verify_child_mode import Client

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--idle-test',action='store_true')
    p.add_argument('--expect-dnd',action='store_true')
    args=p.parse_args()
    report={}
    with Client('COM5',timeout=30) as c:
        c.hello()
        def call(s,f,a=None):
            if f not in ('GetState','FSReadText'):print(s+'.'+f,flush=True)
            try:
                try:return c.call(s,f,a or {})['result']
                except RuntimeError as exc:
                    if str(exc)!='invalid_command: request_id has already been used':raise
                    return c.call(s,f,a or {})['result']
            except Exception:
                c.serial.timeout=.2;chunks=[];end=time.monotonic()+3
                while time.monotonic()<end:chunks.append(c.serial.read(max(1,c.serial.in_waiting)))
                (ROOT/'runtime/device-modes-failure.private.log').write_bytes(b''.join(chunks))
                raise

        def modes():return call('DeviceModes','GetState')
        def wait(fn,timeout=20):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                result=fn()
                if result:return result
                time.sleep(.3)
            raise RuntimeError('Verification condition timed out')
        report['initial']=modes()
        assert report['initial']['timeout_seconds']==600
        if args.expect_dnd:assert report['initial']['do_not_disturb']
        original_volume=report['initial']['resume_volume'] if report['initial']['do_not_disturb'] else call('AudioPlayback','GetVolume')
        try:
            call('DeviceModes','Wake');call('DeviceModes','SetDoNotDisturb',{'Enabled':False})
            wait(lambda:not modes()['audio_pending'])
            call('AudioPlayback','SetVolume',{'Volume':18})
            call('DeviceModes','SetDoNotDisturb',{'Enabled':True})
            report['muted']=wait(lambda:(s:=modes()) and s['do_not_disturb'] and not s['audio_pending'] and not s['pending_save'] and s)
            assert call('AudioPlayback','GetVolume')==0
            call('AudioPlayback','SetVolume',{'Volume':27})
            assert call('AudioPlayback','GetVolume')==0 and modes()['resume_volume']==18
            apps=call('SystemCore','ListApps')
            book=next(a for a in apps if a['manifest']['id']=='local.audiobook')
            call('SystemCore','StartApp',{'AppId':book['app_id']})
            wait(lambda:(active:=call('SystemCore','GetActiveApp')) and active.get('app_id')==book['app_id'] and active.get('state')=='Running')
            time.sleep(.5)
            call('Audiobook','TestTone')
            time.sleep(3)
            report['muted_test_tone']=call('Audiobook','GetState')
            assert report['muted_test_tone']['bytes_written']>0 and not report['muted_test_tone']['error']
            assert call('AudioPlayback','GetVolume')==0
            call('DeviceModes','SetDoNotDisturb',{'Enabled':False})
            wait(lambda:not modes()['audio_pending'])
            assert call('AudioPlayback','GetVolume')==18
            report['restored']=modes()
            call('SystemCore','RequestCloseApp',{'AppId':book['app_id']})
            time.sleep(.5)
            call('DeviceModes','SleepNow')
            report['sleep_now']=wait(lambda:(s:=modes()) and s['screen_asleep'] and s)
            call('DeviceModes','Wake')
            report['wake']=wait(lambda:(s:=modes()) and not s['screen_asleep'] and s)
            assert report['wake']['panel_errors']==0
            apps=call('SystemCore','ListApps')
            weather=next(a for a in apps if a['manifest']['id']=='local.weather')
            assert weather['manifest']['version']=='0.2.6'
            call('SystemCore','StartApp',{'AppId':weather['app_id']})
            def weather_state():return json.loads(call('Storage','FSReadText',{'Path':'/littlefs/weather-state.json'}))
            a=wait(lambda:(s:=weather_state()) and (s.get('fx_probe') or {}).get('tick')==8 and s)
            b=wait(lambda:(s:=weather_state()) and (s.get('fx_probe') or {}).get('tick')==40 and s)
            assert not b['fx_error']
            for s in [a,b]:
                probe=s['fx_probe']
                if isinstance(probe.get('expected'),(int,float)):assert abs(probe['frame']['y']-probe['expected'])<=4,probe
            assert a['fx_probe']['frame']!=b['fx_probe']['frame']
            report['weather_frames']=[a,b]
            print('Actual weather view positions changed; mute, restore and immediate screen sleep/wake passed',flush=True)
            if args.idle_test:
                call('DeviceModes','SetAutoSleep',{'Enabled':True})
                wait(lambda:not modes()['screen_asleep'] and modes()['idle_seconds']<=1)
                started=time.monotonic();last_progress=-1;last_awake=None
                while time.monotonic()-started<720:
                    s=modes()
                    if s['screen_asleep']:
                        assert s['idle_seconds']>=600,s
                        report['idle_elapsed_seconds']=time.monotonic()-started
                        report['automatic_sleep']=s
                        report['last_awake']=last_awake
                        break
                    last_awake=s
                    progress=s['idle_seconds']//30
                    if progress!=last_progress:
                        print('Idle '+str(s['idle_seconds'])+' / 600 seconds',flush=True);last_progress=progress
                    time.sleep(.5)
                else:raise RuntimeError('Full ten minute screen timeout did not occur')
                time.sleep(6)
                report['sleeping_weather']=weather_state()
                assert not report['sleeping_weather']['fx_active']
                call('DeviceModes','Wake')
                wait(lambda:not modes()['screen_asleep'])
                report['resumed_weather']=wait(lambda:(s:=weather_state()) and s.get('fx_active') and s.get('fx_frames',0)>=8 and s)
                print('Full 600 second idle timeout and weather animation resume passed',flush=True)
        finally:
            primary_error=sys.exc_info()[0]
            try:
                call('DeviceModes','SetDoNotDisturb',{'Enabled':False})
                wait(lambda:not modes()['audio_pending'])
                call('AudioPlayback','SetVolume',{'Volume':original_volume})
            except Exception as exc:
                report['cleanup_error']=str(exc)
                if primary_error is None:raise
            finally:
                (ROOT/'runtime/device-modes-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
