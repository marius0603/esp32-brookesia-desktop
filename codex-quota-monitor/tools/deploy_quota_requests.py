"""Stage the request-driven quota update on SD, preserving installed theme assets."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile
from maintenance_client import SharedPowerDiagnosticClient
from deploy_clock_widgets import tree_hash

ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = '/sdcard/apps/local.codex.quota'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM5')
    args = parser.parse_args()
    version = json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps']['local.codex.quota']
    package = ROOT/f'packages/apps/local.codex.quota.debug.{version}.bpk'
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        files = {name:z.read(name) for name in ('app/main.js','res/screens/main.json','res/root.json','manifest.json')}
    stamp = str(time.time_ns())
    base = '/sdcard/resource-backups/quota-requests-'+stamp
    ready, backup, checked = base+'-ready', base+'-previous', base+'-check'
    local = ROOT/'codex-quota-monitor/runtime'/('quota-requests-'+stamp)
    local.mkdir(parents=True)
    with SharedPowerDiagnosticClient(args.port,timeout=35) as c:
        c.hello()
        def f(service,name,args=None):return c.call_timeout(service,name,args or {})['result']
        for service in ('Audiobook','Radio','VoiceAssistant','LocalVoice'):
            assert not f(service,'GetState')['active'], 'Finish active audio first'
        apps = f('SystemCore','ListApps')
        app = next(a for a in apps if a['manifest']['id']=='local.codex.quota')
        before = f('DeviceModes','GetState')
        quota = f('Storage','FSReadText',{'Path':'/littlefs/quota.json'})
        f('SystemCore','StopApp',{'AppId':app['app_id']})
        original = f('SdResources','InspectTree',{'Path':APP_ROOT})
        f('Storage','FSCopyTree',{'From':APP_ROOT,'To':ready,'Overwrite':False})
        assert f('SdResources','InspectTree',{'Path':ready}) == original
        f('Storage','FSMkdir',{'Path':checked})
        hashes = {}
        for number,(name,data) in enumerate(files.items()):
            file = local/str(number);file.write_bytes(data)
            temp = 'quota-requests-'+stamp+'.bin'
            transfer = c.transfer('put',file,'sd-themes/'+temp,False)
            assert transfer['ok'] and transfer['sha256']==hashlib.sha256(data).hexdigest()
            f('Storage','FSCopyTree',{'From':'/sdcard/themes/'+temp,'To':ready+'/'+name,'Overwrite':True})
            f('Storage','FSRemove',{'Path':'/sdcard/themes/'+temp})
            f('Storage','FSCopyTree',{'From':ready+'/'+name,'To':checked+'/'+str(number),'Overwrite':False})
            hashes[str(number)] = data
        assert f('SdResources','InspectTree',{'Path':checked})['sha256']==tree_hash(hashes)
        assert f('SdResources','InspectTree',{'Path':APP_ROOT}) == original
        f('Storage','FSRename',{'From':APP_ROOT,'To':backup})
        try:
            f('Storage','FSRename',{'From':ready,'To':APP_ROOT})
            assert json.loads(f('Storage','FSReadText',{'Path':APP_ROOT+'/manifest.json'}))['package']['version']==version
        except BaseException:
            if f('Storage','FSStat',{'Path':APP_ROOT})['exists']:
                f('Storage','FSRename',{'From':APP_ROOT,'To':ready})
            f('Storage','FSRename',{'From':backup,'To':APP_ROOT})
            raise
        assert f('Storage','FSReadText',{'Path':'/littlefs/quota.json'})==quota
        after = f('DeviceModes','GetState')
        assert before['resume_volume']==after['resume_volume']
        report = {'passed':True,'version':version,'backup':backup,'restart_required':True,
                  'files':list(files),'volume_preserved':True,'quota_preserved':True,
                  'other_apps':{a['manifest']['id']:a['manifest']['version'] for a in apps if a['app_id']!=app['app_id']}}
        (ROOT/'codex-quota-monitor/runtime/quota-requests-deployment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Quota scripts staged and verified; theme assets, quota cache and volume preserved. Restart to register '+version,flush=True)


if __name__=='__main__':main()
