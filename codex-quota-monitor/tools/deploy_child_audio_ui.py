"""Update only the Flash parent UI files; preserve icons, PIN and all app data."""
import hashlib,json,time,zipfile
from pathlib import Path
from maintenance_client import SharedPowerDiagnosticClient
from deploy_clock_widgets import tree_hash
ROOT=Path(__file__).resolve().parents[2]

def main():
    version=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps']['local.childmode']
    with zipfile.ZipFile(ROOT/f'packages/apps/local.childmode.debug.{version}.bpk') as z:
        files={n:z.read(n) for n in ('app/main.js','res/screens/main.json','res/root.json','manifest.json')}
    stamp=str(time.time_ns());backup='/sdcard/resource-backups/child-audio-'+stamp
    local=ROOT/'codex-quota-monitor/runtime'/('child-audio-'+stamp);local.mkdir()
    with SharedPowerDiagnosticClient('COM5',timeout=35) as c:
        c.hello()
        def f(s,n,a=None):return c.call_timeout(s,n,a or {})['result']
        firmware=f('DeviceModes','GetState')['firmware_version'].split('-s3.')
        assert len(firmware)==2 and int(firmware[-1])>=73,'Install matching s3.73 firmware first'
        end=time.monotonic()+90
        while True:
            apps=f('SystemCore','ListApps');app=next((a for a in apps if a['manifest']['id']=='local.childmode'),None)
            if app:break
            assert time.monotonic()<end,'Waiting for parent app';time.sleep(1)
        f('SystemCore','StopApp',{'AppId':app['app_id']})
        before=f('ChildMode','GetState');root='/littlefs/apps/local.childmode'
        f('Storage','FSCopyTree',{'From':root,'To':backup,'Overwrite':False})
        check=backup+'-check';f('Storage','FSMkdir',{'Path':check});checked={}
        for number,(name,data) in enumerate(files.items()):
            path=local/str(number);path.write_bytes(data);temp='child-audio-'+stamp+'.bin'
            result=c.transfer('put',path,'sd-themes/'+temp,False);assert result['ok'] and result['sha256']==hashlib.sha256(data).hexdigest()
            f('Storage','FSCopyTree',{'From':'/sdcard/themes/'+temp,'To':root+'/'+name,'Overwrite':True})
            f('Storage','FSRemove',{'Path':'/sdcard/themes/'+temp})
            f('Storage','FSCopyTree',{'From':root+'/'+name,'To':check+'/'+str(number),'Overwrite':False});checked[str(number)]=data
        assert f('SdResources','InspectTree',{'Path':check})['sha256']==tree_hash(checked)
        after=f('ChildMode','GetState')
        for name in ('configured','enabled','max_volume','daily_minutes','night_enabled','night_start','night_end',
                     'allow_audiobook','allow_songs','allow_radio','radio_allowed_stations'):
            assert after[name]==before[name],name
        (ROOT/'codex-quota-monitor/runtime/child-audio-ui-deployment.json').write_text(json.dumps({'passed':True,'version':version,'backup':backup,'pin_preserved':after['configured']},indent=2),encoding='utf-8')
    print('Parent authorization panel updated; existing policy and a backup of the old UI were verified.',flush=True)
if __name__=='__main__':main()
