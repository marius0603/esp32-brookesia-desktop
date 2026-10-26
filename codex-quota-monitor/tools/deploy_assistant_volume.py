"""Update assistant 0.1.1 code/manifest with SD backups; retain icons and settings."""
import argparse,hashlib,json,time
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--port',default='COM5');a=p.parse_args()
    source=a.repo/'brookesia-apps/voice-assistant/src'
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['package']['id']=='local.voiceassistant' and manifest['package']['version']=='0.1.1'
    backup='/sdcard/resource-backups/assistant-volume-'+datetime.now().strftime('%Y%m%d-%H%M%S')
    report={'complete':False,'backup':backup,'files':[],'restart_required':True}
    with StoryClient(a.port,timeout=30) as c:
        c.hello()
        def call(s,f,p=None):return c.call(s,f,p or {})['result']
        enabled=call('OfflineVoice','GetState')['enabled']
        call('VoiceAssistant','Disconnect');call('OfflineVoice','SetEnabled',{'Enabled':False})
        try:
            end=time.monotonic()+10
            while call('OfflineVoice','GetState')['microphone_open']:
                assert time.monotonic()<end;time.sleep(.1)
            app=next(v for v in call('SystemCore','ListApps') if v['manifest']['id']=='local.voiceassistant')
            if app['state'] in ('Running','Paused','Starting'):
                call('SystemCore','RequestCloseApp',{'AppId':app['app_id']});time.sleep(1)
            call('Storage','FSMkdir',{'Path':backup})
            for name in ('manifest.json','app/main.js'):
                local=source/name;target='/littlefs/apps/local.voiceassistant/'+name
                assert call('Storage','FSStat',{'Path':target})['exists'],target
                call('Storage','FSCopyTree',{'From':target,'To':backup+'/'+name.replace('/','-'),'Overwrite':False})
                digest=hashlib.sha256(local.read_bytes()).hexdigest()
                done=c.transfer('put',local,'assistant-volume-update.bin',True);assert done['sha256']==digest
                call('Storage','FSRename',{'From':'/littlefs/usb/assistant-volume-update.bin','To':target})
                assert call('Storage','FSStat',{'Path':target})['size']==local.stat().st_size
                report['files'].append({'path':target,'sha256':digest})
            report['complete']=True
        finally:
            call('OfflineVoice','SetEnabled',{'Enabled':enabled})
            (ROOT/'runtime/assistant-volume-deployment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Assistant 0.1.1 code verified; restart to refresh app metadata.',flush=True)
if __name__=='__main__':main()
