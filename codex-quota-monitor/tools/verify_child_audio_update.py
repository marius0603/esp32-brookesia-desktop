"""Verify retained parent settings after upgrading from the shared audio switch."""
import argparse,json,time
from pathlib import Path
from maintenance_client import SharedPowerDiagnosticClient
ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='COM5')
    parser.add_argument('--before',type=Path,required=True,help='Snapshot from the previous firmware with a shared audio switch')
    args=parser.parse_args()
    before=json.loads(args.before.read_text(encoding='utf-8'))
    old_child=before['states']['ChildMode']
    versions=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))
    with SharedPowerDiagnosticClient(args.port,timeout=35) as c:
        c.hello()
        def f(s,n,a=None):return c.call_timeout(s,n,a or {})['result']
        end=time.monotonic()+90
        while True:
            apps=f('SystemCore','ListApps')
            actual={a['manifest']['id']:a['manifest']['version'] for a in apps}
            if len(apps)==len(before['apps']) and all(actual.get(id)==versions['apps'][id] for id in ('local.childmode','local.radio')):break
            assert time.monotonic()<end,'Waiting for app discovery';time.sleep(1)
        modes=f('DeviceModes','GetState');child=f('ChildMode','GetState')
        assert modes['firmware_version']==versions['firmware']
        for key in ('configured','enabled','allow_audiobook','allow_weather','allow_clock','allow_assistant','allow_learning',
                    'max_volume','daily_minutes','night_enabled','night_start','night_end'):
            assert child[key]==old_child[key],key
        assert child['allow_radio']==child['allow_songs']==old_child['allow_audiobook']
        assert child['radio_allowed_stations']==[]
        catalog=f('ChildMode','GetRadioStations')['stations']
        display=json.loads((ROOT/'brookesia-apps/radio/src/app/catalog.json').read_text(encoding='utf-8'))
        assert [s['id'] for s in catalog]==[s['id'] for s in display]
        for key in ('resume_volume','desktop_theme_index','auto_deep_sleep_minutes','quiet_hours_enabled','quiet_start_minute','quiet_end_minute'):
            assert modes[key]==before['states']['DeviceModes'][key],key
        for a in apps:
            id=a['manifest']['id']
            old=next(v for v in before['apps'] if v['manifest']['id']==id)
            assert a['manifest']['version']==(versions['apps'][id] if id in ('local.childmode','local.radio') else old['manifest']['version'])
        assert f('Audiobook','List')['tracks']==before['stories']
        assert f('Audiobook','ListSongs')['tracks']==before['songs']
        try:
            f('ChildMode','Configure',{'Token':'invalid-child-audio-test','Settings':{'radio_allowed_stations':[catalog[0]['id']]}})
        except RuntimeError as exc:
            assert '请重新验证家长 PIN' in str(exc)
        else:raise AssertionError('Parent authorization must still be required')
        assert f('ChildMode','GetState')['radio_allowed_stations']==[]
        available=f('Radio','GetState')['available_stations']
        if child['enabled']:
            assert not available
        else:
            assert all(s['id'] in available for s in catalog)
        f('DeviceModes','Wake')
        def start(id):
            app=next(a for a in apps if a['manifest']['id']==id)
            f('SystemCore','StartApp',{'AppId':app['app_id']});time.sleep(1)
            active=f('SystemCore','GetActiveApp');assert active['state']=='Running' and not active['last_error'],active
            return app['app_id']
        if not child['enabled']:
            radio_id=start('local.radio')
            assert not f('Radio','GetState')['active']
            f('SystemCore','StopApp',{'AppId':radio_id})
        start('local.childmode')
        report={'passed':True,'firmware':versions['firmware'],'child_app':versions['apps']['local.childmode'],
                'apps_preserved':len(apps),'stories_preserved':len(before['stories']),'songs_preserved':len(before['songs']),
                'pin_configured_preserved':child['configured'],'parent_authorization_required':True,'audio_permission':child['allow_audiobook'],
                'empty_allowlist_after_migration':True,'physical_child_mode_check':'requires existing parent PIN'}
        (ROOT/'codex-quota-monitor/runtime/child-audio-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
