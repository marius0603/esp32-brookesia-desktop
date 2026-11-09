"""Check native desktop CPU/RAM telemetry, transparent style and app visibility."""
import argparse
import json
from pathlib import Path
import re
import time
from maintenance_client import SharedPowerDiagnosticClient

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='COM5')
    parser.add_argument('--capture-baseline',action='store_true',help='Save app versions and preferences before updating; no device writes')
    args=parser.parse_args()
    baseline=ROOT/'codex-quota-monitor/runtime/resource-monitor-preservation.json'
    if args.capture_baseline:
        with SharedPowerDiagnosticClient(args.port,timeout=30) as client:
            client.hello()
            apps=client.call_timeout('SystemCore','ListApps',{})['result']
            state=client.call_timeout('DeviceModes','GetState',{})['result']
        saved={'apps':{a['manifest']['id']:a['manifest']['version'] for a in apps},'firmware':state['firmware_version']}
        for key,name in [('volume','resume_volume'),('theme','desktop_theme_index'),('quiet_enabled','quiet_hours_enabled'),
                         ('quiet_start','quiet_start_minute'),('quiet_end','quiet_end_minute'),('auto_deep_sleep_minutes','auto_deep_sleep_minutes')]:
            saved[key]=state[name]
        baseline.parent.mkdir(parents=True,exist_ok=True)
        baseline.write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Saved pre-update preservation baseline',flush=True)
        return
    original=json.loads(baseline.read_text(encoding='utf-8'))
    expected=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['firmware']
    report={'passed':False,'desktop_samples':[],'clock_samples':[]}
    with SharedPowerDiagnosticClient(args.port,timeout=30) as client:
        client.hello()
        def f(s,n,a=None):return client.call_timeout(s,n,a or {})['result']
        end=time.monotonic()+90
        while True:
            apps=f('SystemCore','ListApps')
            if len(apps)==len(original['apps']) and any(a['manifest']['id']=='brookesia.system.super.shell' and a['state']=='Running' for a in apps):break
            assert time.monotonic()<end,'Desktop startup timed out'
            time.sleep(1)
        modes=f('DeviceModes','GetState')
        assert modes['firmware_version']==expected
        assert {a['manifest']['id']:a['manifest']['version'] for a in apps}==original['apps']
        for name,key in [('resume_volume','volume'),('desktop_theme_index','theme'),('quiet_hours_enabled','quiet_enabled'),('quiet_start_minute','quiet_start'),('quiet_end_minute','quiet_end'),('auto_deep_sleep_minutes','auto_deep_sleep_minutes')]:
            assert modes[name]==original[key],name
        assert not modes['screen_locked']
        f('DeviceModes','Wake')
        shell=next(a for a in apps if a['manifest']['id']=='brookesia.system.super.shell')
        clock=next(a for a in apps if a['manifest']['id']=='local.flipclock')
        def desktop():
            active=f('SystemCore','GetActiveApp')
            if active.get('app_id') and active['app_id']!=shell['app_id']:
                f('SystemCore','StopApp',{'AppId':active['app_id']})
            f('SystemCore','StartApp',{'AppId':shell['app_id']});time.sleep(.5)
        def native_layers():return f('DeviceModes','GetWeatherLayers')['layers']
        def layers():return [v for v in native_layers() if v['kind'] in ('top_status','resource_status')]
        def sample():
            v=f('DeviceModes','GetResourceUsage')
            assert v['cpu_cores']==2 and 0<=v['cpu_percent']<=100
            assert abs(v['cpu_percent']-(v['cpu_core0_percent']+v['cpu_core1_percent'])/2)<=.02
            total,free=v['ram_total_bytes'],v['ram_free_bytes']
            assert total>8*1024*1024 and 0<=free<=total
            assert abs(v['ram_percent']-((total-free)*10000//total)/100)<.001
            assert v['ram_scope']=='byte_addressable_heap_including_psram'
            return v
        desktop()
        for _ in range(5):report['desktop_samples'].append(sample());time.sleep(1.1)
        assert report['desktop_samples'][-1]['sample_count']>report['desktop_samples'][0]['sample_count']+2
        visible=layers();resource=next(v for v in visible if v['kind']=='resource_status');status=next(v for v in visible if v['kind']=='top_status')
        assert re.fullmatch(r'CPU \d+%    RAM \d+%',resource['text']) and resource['height']<=26
        assert 0<=resource['x']<=16 and 0<=resource['y']<=16
        assert resource['x']+resource['width']<=status['x'],'Resource badge overlaps sound/battery'
        assert abs(status['x']-(resource['x']+resource['width']+20))<=2,'Sound/battery must follow RAM with a wider gap'
        assert status['y']==resource['y']
        headers=[v for v in native_layers() if v['kind']=='system_header']
        for header in headers:
            assert status['x']+status['width']<=header['x'],'Telemetry overlaps existing Wi-Fi/time'
        report['native_header']=headers
        expected_color=0xa7f2ff if original['theme']==1 else 0xfff0d4
        for label in visible:
            assert label['background_opacity']==0 and label['text_rgb']==expected_color and not label['clickable'],label
        report['desktop_labels']=visible
        try:
            f('SystemCore','StartApp',{'AppId':clock['app_id']});time.sleep(1)
            assert layers()==[],'Desktop status must be hidden in apps'
            for _ in range(5):report['clock_samples'].append(sample());time.sleep(1.1)
            active=f('SystemCore','GetActiveApp')
            assert active['app_id']==clock['app_id'] and active['state']=='Running' and not active['last_error']
        finally:
            desktop()
        assert len(layers())==2,'Desktop labels did not return'
        assert len(f('Audiobook','List')['tracks'])==30
        assert len(f('Audiobook','ListSongs')['tracks'])==20
        report.update(passed=True,firmware=expected,apps_preserved=len(apps),stories_preserved=30,songs_preserved=20,
                      volume_preserved=modes['resume_volume'],app_hide_and_return=True)
    (ROOT/'codex-quota-monitor/runtime/resource-monitor-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
