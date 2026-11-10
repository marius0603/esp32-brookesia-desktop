"""Stage the three audio UI updates on SD, retaining full old trees and app data."""
import hashlib,json,time,zipfile
from pathlib import Path
from maintenance_client import SharedPowerDiagnosticClient
from deploy_clock_widgets import tree_hash
ROOT=Path(__file__).resolve().parents[2]

def main():
    versions=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps']
    report={'passed':False,'apps':[]};output=ROOT/'codex-quota-monitor/runtime/audio-theme-deployment.json'
    with SharedPowerDiagnosticClient('COM5',timeout=35) as client:
        client.hello()
        def f(s,n,a=None):return client.call_timeout(s,n,a or {})['result']
        def inspect(p):return f('SdResources','InspectTree',{'Path':p})
        modes=f('DeviceModes','GetState')
        for service in ('Audiobook','Radio','VoiceAssistant','LocalVoice'):assert not f(service,'GetState')['active'],'Finish current audio first'
        apps=f('SystemCore','ListApps');report['before_versions']={a['manifest']['id']:a['manifest']['version'] for a in apps}
        report['volume']=modes['resume_volume'];report['theme']=modes['desktop_theme_index']
        f('DeviceModes','Wake');f('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
        try:
            active=f('SystemCore','GetActiveApp')
            if active.get('app_id'):f('SystemCore','StopApp',{'AppId':active['app_id']})
            for id in ('local.nurserysongs','local.audiobook','local.radio'):
                app=next(a for a in apps if a['manifest']['id']==id);f('SystemCore','StopApp',{'AppId':app['app_id']})
                root='/sdcard/apps/'+id;stamp=str(time.time_ns());base='/sdcard/resource-backups/audio-theme-'+stamp;ready=base+'-ready';retired=base+'-previous'
                original=inspect(root);f('Storage','FSCopyTree',{'From':root,'To':ready,'Overwrite':False});assert inspect(ready)==original
                with zipfile.ZipFile(ROOT/f'packages/apps/{id}.debug.{versions[id]}.bpk') as z:files={n:z.read(n) for n in z.namelist()}
                localroot=ROOT/'codex-quota-monitor/runtime'/('audio-theme-'+stamp);localroot.mkdir()
                check=base+'-check';f('Storage','FSMkdir',{'Path':check});checked={}
                for number,name in enumerate(('app/main.js','res/screens/main.json','res/root.json','manifest.json')):
                    data=files[name];local=localroot/str(number);local.write_bytes(data)
                    temp='audio-theme-'+stamp+'.bin';r=client.transfer('put',local,'sd-themes/'+temp,False);assert r['ok'] and r['sha256']==hashlib.sha256(data).hexdigest()
                    f('Storage','FSCopyTree',{'From':'/sdcard/themes/'+temp,'To':ready+'/'+name,'Overwrite':True});f('Storage','FSRemove',{'Path':'/sdcard/themes/'+temp})
                    f('Storage','FSCopyTree',{'From':ready+'/'+name,'To':check+'/'+str(number),'Overwrite':False})
                    checked[str(number)]=data
                assert inspect(check)['sha256']==tree_hash(checked)
                for directory in ('data','files','cache'):
                    if f('Storage','FSStat',{'Path':root+'/'+directory})['exists']:assert inspect(root+'/'+directory)==inspect(ready+'/'+directory)
                staged=inspect(ready);assert inspect(root)==original
                f('Storage','FSRename',{'From':root,'To':retired})
                try:
                    f('Storage','FSRename',{'From':ready,'To':root});assert inspect(root)==staged
                except BaseException:
                    if f('Storage','FSStat',{'Path':root})['exists']:f('Storage','FSRename',{'From':root,'To':ready})
                    f('Storage','FSRename',{'From':retired,'To':root});raise
                report['apps'].append({'id':id,'version':versions[id],'backup':retired,'tree_sha256':staged['sha256']})
                output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('Updated '+id,flush=True)
            report['passed']=True
        finally:
            f('DeviceModes','SetAutoDeepSleep',{'Minutes':modes['auto_deep_sleep_minutes']})
            assert f('DeviceModes','GetState')['resume_volume']==modes['resume_volume']
            output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Three SD app trees verified. Restart to load the new versions.',flush=True)
if __name__=='__main__':main()
