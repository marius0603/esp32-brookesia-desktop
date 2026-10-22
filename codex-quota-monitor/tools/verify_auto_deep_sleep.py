"""Check presets, persistence and the idle trigger using a temporary 5 s test.

The accelerated path uses the production idle poll and audio guard, but adds
a 20 s RTC recovery timer. It never persists a short timeout.
Do not touch the board during this test. Original preferences are restored.
"""
import json
from pathlib import Path
import time
import serial
from verify_child_mode import Client

ROOT=Path(__file__).resolve().parents[1]
PRESETS=(0,10,20,30,60,120,240)


def main():
    original=None
    original_volume=None
    report={'passed':False,'presets':[]}
    def connect():
        client=Client('COM5',timeout=15)
        try:client.hello()
        except Exception:
            client.serial.close()
            raise
        return client
    def call(c,s,f,p=None):return c.call(s,f,p or {})['result']
    def state(c):return call(c,'DeviceModes','GetState')
    def saved(c):
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            value=state(c)
            if value['preferences_loaded'] and not value['pending_save']:return value
            time.sleep(.1)
        raise TimeoutError('Preference save did not finish')
    try:
        with connect() as c:
            initial=saved(c)
            original=initial['auto_deep_sleep_minutes'];original_volume=initial['resume_volume']
            for value in PRESETS:
                call(c,'DeviceModes','SetAutoDeepSleep',{'Minutes':value})
                current=saved(c)
                assert current['auto_deep_sleep_minutes']==value,current
                assert max(0,value*60-3)<=current['auto_deep_sleep_remaining_seconds']<=value*60,current
                report['presets'].append(value)
            for bad in (-1,5,10.5,241):
                try:call(c,'DeviceModes','SetAutoDeepSleep',{'Minutes':bad})
                except RuntimeError as error:
                    assert 'Use 0,10,20,30,60,120,240' in str(error),str(error)
                else:raise AssertionError('Invalid preset accepted')
            # The app holds the audio service alive. A transient USB-only binding
            # stops its worker as soon as TestTone returns, before any playback.
            apps=call(c,'SystemCore','ListApps')
            app=next(a for a in apps if a['manifest']['id']=='local.audiobook')
            call(c,'SystemCore','StartApp',{'AppId':app['app_id']});time.sleep(1)
            call(c,'AudioPlayback','SetVolume',{'Volume':original_volume})
            call(c,'DeviceModes','SetAutoDeepSleep',{'Minutes':20});before=saved(c)
            report['preserved']={k:before[k] for k in ('auto_deep_sleep_minutes','auto_sleep_enabled','quiet_hours_enabled','quiet_start_minute','quiet_end_minute','resume_volume')}
            entries=before['deep_sleep']['entries']
            # TestTone is a fixed two second synthetic sound, no microphone upload.
            call(c,'Audiobook','TestTone')
            call(c,'DeviceModes','TestIdleDeepSleep')
            time.sleep(.4)
            busy=state(c);assert busy['auto_deep_sleep_audio_busy'] and busy['test_idle_deep_sleep'],busy
            assert not busy['deep_sleep']['pending'],busy
            deadline=time.monotonic()+6
            while state(c)['auto_deep_sleep_audio_busy']:
                assert time.monotonic()<deadline
                time.sleep(.1)
            report['audio_deferral']=True
            # Stay connected for four quiet seconds, confirming no early sleep.
            time.sleep(3.6)
            waiting=state(c)
            assert waiting['test_idle_deep_sleep'] and not waiting['deep_sleep']['pending'],waiting
        print('All seven presets, invalid values and audio deferral checked; waiting for idle sleep/recovery',flush=True)
        started=time.monotonic()
        while time.monotonic()-started<28:time.sleep(1)
        deadline=started+95
        while time.monotonic()<deadline:
            try:
                with connect() as c:after=saved(c)
            except (OSError,serial.SerialException,TimeoutError):
                time.sleep(1);continue
            deep=after['deep_sleep']
            assert not deep['error'] and deep['entries']==entries+1 and deep['wake_cause']==4,deep
            assert not after['test_idle_deep_sleep']
            assert {k:after[k] for k in report['preserved']}==report['preserved']
            report.update({'idle_trigger_verified':True,'timer_wake':deep,'passed':True})
            print('Idle-triggered real deep sleep and saved 20 minute preset survived RTC wake',flush=True)
            break
        else:raise TimeoutError('Idle deep-sleep recovery did not finish')
    finally:
        if original is not None:
            with connect() as c:
                call(c,'DeviceModes','SetAutoDeepSleep',{'Minutes':original})
                if original_volume is not None:call(c,'AudioPlayback','SetVolume',{'Volume':original_volume})
                assert saved(c)['auto_deep_sleep_minutes']==original
        (ROOT/'runtime/auto-deep-sleep-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
