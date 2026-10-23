"""Verify SD stories and the native fade/stop path with a ten second timer.

Temporarily disables DND/automatic deep sleep for audible diagnostics, restores
all captured preferences, and never changes parent controls or their PIN.
"""
import json,time
from pathlib import Path
from verify_child_mode import Client
ROOT=Path(__file__).resolve().parents[1]
STORIES=('/sdcard/audiobooks/bedtime/01-xiaoma-yueliang.mp3','/sdcard/audiobooks/bedtime/02-gudong.mp3')
def main():
    report={'passed':False};original=None
    with Client('COM5',timeout=30) as c:
        c.hello()
        def call(s,f,p=None):return c.call(s,f,p or {})['result']
        def modes():return call('DeviceModes','GetState')
        def book():return call('Audiobook','GetState')
        def wait_done():
            until=time.monotonic()+18
            while time.monotonic()<until:
                s=book()
                if not s['active'] and s['sleep_completed']:
                    assert s['state']=='SleepEnded' and not s['error'],s
                    return s
                time.sleep(.2)
            raise TimeoutError('Story timer did not stop playback')
        try:
            original=modes();call('DeviceModes','Wake')
            apps=call('SystemCore','ListApps')
            app=next(a for a in apps if a['manifest']['id']=='local.audiobook')
            call('SystemCore','StartApp',{'AppId':app['app_id']});time.sleep(1)
            call('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
            call('DeviceModes','SetQuietHours',{'Enabled':False,'StartMinute':original['quiet_start_minute'],'EndMinute':original['quiet_end_minute']})
            call('DeviceModes','SetDoNotDisturb',{'Enabled':False})
            call('AudioPlayback','SetVolume',{'Volume':original['resume_volume']});time.sleep(.3)
            baseline=modes();assert baseline['volume_keys_ready'],baseline
            report['baseline_brightness']=baseline['brightness_percent']
            library=call('Audiobook','List');assert all(p in [x['path'] for x in library['tracks']] for p in STORIES)
            report['stories']=[]
            for path in STORIES:
                call('Audiobook','Play',{'Path':path,'Position':0});time.sleep(1.5)
                s=book();assert s['state']=='Playing' and s['bytes_written']>0 and s['position']>=1,s
                report['stories'].append({'path':path,'duration':s['duration'],'bytes_written':s['bytes_written']})
                call('Audiobook','Pause')
            for minutes in (15,30,45):
                call('Audiobook','SetSleepTimer',{'Minutes':minutes});s=book()
                assert s['sleep_active'] and minutes*60-2<=s['sleep_remaining_seconds']<=minutes*60,s
            for bad in (-1,10,15.5,60):
                try:call('Audiobook','SetSleepTimer',{'Minutes':bad})
                except RuntimeError as e:assert 'Use 0,15,30 or 45' in str(e)
                else:raise AssertionError('Invalid story timer accepted')
            # Timer survives an explicit chapter change without restarting.
            call('Audiobook','SetSleepTimer',{'Minutes':15});time.sleep(1.2)
            before=book()['sleep_remaining_seconds'];call('Audiobook','Play',{'Path':STORIES[0],'Position':0})
            assert book()['sleep_remaining_seconds']<=before
            call('Audiobook','TestSleepTimer');time.sleep(4)
            faded=book();dim=modes()
            assert 0<faded['sleep_gain_per_mille']<1000 and faded['sleep_fading'],faded
            assert dim['brightness_percent']<baseline['brightness_percent'],dim
            assert dim['resume_volume']==original['resume_volume'],dim
            report['fade']={'gain':faded['sleep_gain_per_mille'],'brightness':dim['brightness_percent']}
            call('Audiobook','SetSleepTimer',{'Minutes':0});time.sleep(.3)
            assert book()['sleep_gain_per_mille']==1000 and modes()['brightness_percent']==baseline['brightness_percent']
            report['cancel_restores']=True
            # The clock takes foreground while the audiobook is paused; the native
            # timer must still finish without visible JS polling.
            call('Audiobook','Pause');call('Audiobook','TestSleepTimer');count=book()['goodnight_count']
            clock=next(a for a in apps if a['manifest']['id']=='local.flipclock')
            call('SystemCore','StartApp',{'AppId':clock['app_id']})
            finished=wait_done();time.sleep(.3)
            assert finished['goodnight_played'] and finished['goodnight_count']==count+1,finished
            assert modes()['screen_asleep'] and modes()['brightness_percent']==baseline['brightness_percent']
            assert modes()['resume_volume']==original['resume_volume']
            report['background_paused_completion']=True;report['goodnight']=finished
            call('DeviceModes','Wake');call('SystemCore','StartApp',{'AppId':app['app_id']})
            call('Audiobook','Play',{'Path':STORIES[1],'Position':0})
            call('DeviceModes','SetDoNotDisturb',{'Enabled':True});time.sleep(.3)
            call('Audiobook','TestSleepTimer');count=book()['goodnight_count']
            silent=wait_done();assert not silent['goodnight_played'] and silent['goodnight_count']==count,silent
            report['dnd_skips_goodnight']=True
            report['rotation_stack_free']=call('AutoRotation','GetState')['stack_free_min_bytes']
            assert report['rotation_stack_free']>=768,report
            report['passed']=True
        finally:
            if original is not None:
                call('Audiobook','SetSleepTimer',{'Minutes':0});call('Audiobook','Stop')
                call('DeviceModes','SetQuietHours',{'Enabled':original['quiet_hours_enabled'],'StartMinute':original['quiet_start_minute'],'EndMinute':original['quiet_end_minute']})
                call('DeviceModes','SetDoNotDisturb',{'Enabled':original['manual_do_not_disturb']})
                call('AudioPlayback','SetVolume',{'Volume':original['resume_volume']})
                call('DeviceModes','SetAutoDeepSleep',{'Minutes':original['auto_deep_sleep_minutes']})
                call('DeviceModes','Wake')
            (ROOT/'runtime/story-sleep-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'stories':report.get('stories'),'fade':report.get('fade'),'cancel_restores':report.get('cancel_restores'),'background_paused_completion':report.get('background_paused_completion'),'dnd_skips_goodnight':report.get('dnd_skips_goodnight')},ensure_ascii=False))
if __name__=='__main__':main()
