"""Verify retained parent settings and the updated shared audio policy, without a PIN."""
import json,time
from pathlib import Path
from maintenance_client import SharedPowerDiagnosticClient
ROOT=Path(__file__).resolve().parents[2]

def main():
    before=json.loads((ROOT/'codex-quota-monitor/runtime/child-audio-before.json').read_text(encoding='utf-8'))
    versions=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))
    with SharedPowerDiagnosticClient('COM5',timeout=35) as c:
        c.hello()
        def f(s,n,a=None):return c.call_timeout(s,n,a or {})['result']
        end=time.monotonic()+90
        while True:
            apps=f('SystemCore','ListApps')
            if len(apps)==len(before['apps']) and any(a['manifest']['id']=='local.childmode' and a['manifest']['version']==versions['apps']['local.childmode'] for a in apps):break
            assert time.monotonic()<end,'Waiting for app discovery';time.sleep(1)
        modes=f('DeviceModes','GetState');child=f('ChildMode','GetState')
        assert modes['firmware_version']==versions['firmware']
        for key in ('configured','enabled','allow_audiobook','allow_weather','allow_clock','allow_assistant','allow_learning',
                    'max_volume','daily_minutes','night_enabled','night_start','night_end'):
            assert child[key]==before['states']['ChildMode'][key],key
        assert child['allow_radio']==child['allow_songs']==child['allow_audiobook']
        for key in ('resume_volume','desktop_theme_index','auto_deep_sleep_minutes','quiet_hours_enabled','quiet_start_minute','quiet_end_minute'):
            assert modes[key]==before['states']['DeviceModes'][key],key
        for a in apps:
            id=a['manifest']['id']
            old=next(v for v in before['apps'] if v['manifest']['id']==id)
            assert a['manifest']['version']==(versions['apps'][id] if id=='local.childmode' else old['manifest']['version'])
        assert f('Audiobook','List')['tracks']==before['stories']
        assert f('Audiobook','ListSongs')['tracks']==before['songs']
        try:
            f('ChildMode','Configure',{'Token':'invalid-child-audio-test','Settings':{'enabled':True}})
        except RuntimeError as exc:
            assert '请重新验证家长 PIN' in str(exc)
        else:raise AssertionError('Parent authorization must still be required')
        assert f('ChildMode','GetState')['enabled']==child['enabled']
        f('DeviceModes','Wake')
        app=next(a for a in apps if a['manifest']['id']=='local.childmode')
        f('SystemCore','StartApp',{'AppId':app['app_id']});time.sleep(1)
        active=f('SystemCore','GetActiveApp');assert active['state']=='Running' and not active['last_error'],active
        report={'passed':True,'firmware':versions['firmware'],'child_app':versions['apps']['local.childmode'],
                'apps_preserved':len(apps),'stories_preserved':len(before['stories']),'songs_preserved':len(before['songs']),
                'pin_configured_preserved':child['configured'],'parent_authorization_required':True,'audio_permission':child['allow_audiobook'],
                'physical_child_mode_check':'awaiting parent entry on device'}
        (ROOT/'codex-quota-monitor/runtime/child-audio-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
