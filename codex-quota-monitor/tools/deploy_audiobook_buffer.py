"""Install only the 0.3.5 script/manifest; preserve theme and all media resources."""
import argparse,hashlib,json,time,zipfile
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',required=True)
    p.add_argument('--stage-for-firmware-update',action='store_true',help='Do not launch the app until the companion s3.39 firmware is installed')
    a=p.parse_args();package=ROOT/'packages/apps/local.audiobook.debug.0.3.5.bpk'
    report={'passed':False,'restart_required':True,'backup':'/sdcard/resource-backups/audiobook-buffer-'+datetime.now().strftime('%Y%m%d-%H%M%S')}
    folder=ROOT/'codex-quota-monitor/runtime/audiobook-buffer-files';folder.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(package) as z:
        assert json.loads(z.read('manifest.json'))['package']['version']=='0.3.5'
        files={name:z.read(name) for name in ('app/main.js','manifest.json')}
    with StoryClient(a.port,timeout=30) as c:
        c.hello()
        def f(s,n,p=None):return c.call(s,n,p or {})['result']
        before=f('Audiobook','GetState')
        assert not before['sleep_active'],'Preserve the running sleep timer'
        assert not f('DeviceModes','GetState')['screen_locked'],'Unlock on the device first'
        if not a.stage_for_firmware_update:assert before.get('pcm_buffer_bytes')==65536,'Install s3.39 first'
        app=next(x for x in f('SystemCore','ListApps') if x['manifest']['id']=='local.audiobook')
        f('SystemCore','StopApp',{'AppId':app['app_id']})
        report['files']={}
        for name,data in files.items():
            target='/littlefs/apps/local.audiobook/'+name
            f('Storage','FSCopyTree',{'From':target,'To':report['backup']+'/'+Path(name).name,'Overwrite':False})
            local=folder/(Path(name).name+'.bin');local.write_bytes(data)
            destination='sd-themes/story-buffer-update/'+local.name
            result=c.transfer('put',local,destination,True)
            assert result['ok'] and result['sha256']==hashlib.sha256(data).hexdigest()
            staged='/sdcard/themes/story-buffer-update/'+local.name
            f('Storage','FSCopyTree',{'From':staged,'To':target,'Overwrite':True})
            installed=f('Storage','FSReadText',{'Path':target}).encode('utf-8')
            assert hashlib.sha256(installed).hexdigest()==hashlib.sha256(data).hexdigest()
            f('Storage','FSRemove',{'Path':staged})
            report['files'][name]=hashlib.sha256(data).hexdigest()
        report['passed']=True
    (ROOT/'codex-quota-monitor/runtime/audiobook-buffer-deployment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Installed verified 0.3.5 files. Reboot with s3.39 before opening the app.',flush=True)

if __name__=='__main__':main()
