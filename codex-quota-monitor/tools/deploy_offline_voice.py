"""Deploy pinned ESP-SR SD models, offline PCM and Settings without erasing user data."""
import argparse,hashlib,json,time
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--port',default='COM5');a=p.parse_args()
    resources=a.repo/'resources/offline-voice'
    models=json.loads((resources/'models.json').read_text())
    assert models['esp_sr']=='2.4.5'
    component=a.repo.parent/'esp-brookesia-v08/examples/system/super_s3_216/managed_components/espressif__esp-sr'
    if not component.exists():component=a.repo/'esp-brookesia-v08/examples/system/super_s3_216/managed_components/espressif__esp-sr'
    files=[]
    for name,size,digest in models['models']:
        family='multinet_model' if name.startswith('mn') else 'wakenet_model'
        files.append((component/'model'/family/name,'models/'+name,size,digest))
    for name,entry in json.loads((resources/'audio.json').read_text())['files'].items():
        files.append((resources/name,name,entry['bytes'],entry['sha256']))
    for local,name,size,digest in files:
        assert local.stat().st_size==size and hashlib.sha256(local.read_bytes()).hexdigest()==digest,name
    journal=ROOT/'runtime/offline-voice-deployment.json'
    previous=json.loads(journal.read_text()).get('files',[]) if journal.exists() else []
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S');backup='/sdcard/resource-backups/offline-voice-'+stamp
    wanted={('/sdcard/offline-voice/'+name,size,digest) for _,name,size,digest in files}
    kept=[v for v in previous if (v['path'],v['bytes'],v['sha256']) in wanted]
    report={'backup':backup,'files':kept,'restart_required':True}
    with StoryClient(a.port,timeout=30) as c:
        c.hello()
        def call(s,f,p=None):return c.call(s,f,p or {})['result']
        call('OfflineVoice','GetState');call('OfflineVoice','SetEnabled',{'Enabled':False})
        for _ in range(80):
            if not call('OfflineVoice','GetState')['microphone_open']:break
            time.sleep(.1)
        else:raise RuntimeError('Offline microphone did not stop')
        call('Storage','FSMkdir',{'Path':backup})
        for local,name,size,digest in files:
            target='/sdcard/offline-voice/'+name
            stat=call('Storage','FSStat',{'Path':target})
            verified=next((v for v in previous if v['path']==target and v['sha256']==digest and v['bytes']==size),None)
            if not (stat['exists'] and stat['size']==size and verified):
                if stat['exists']:
                    copy=backup+'/'+name.replace('/','-')
                    call('Storage','FSCopyTree',{'From':target,'To':copy,'Overwrite':False})
                    assert call('Storage','FSStat',{'Path':copy})['size']==stat['size']
                    # FAT rename cannot replace a file. The exact previous file
                    # is backed up before removal; all paths stay in this module.
                    call('Storage','FSRemove',{'Path':target})
                done=c.transfer('put',local,'offline-voice/'+name,True)
                assert done['sha256']==digest and call('Storage','FSStat',{'Path':target})['size']==size,name
            report['files']=[v for v in report['files'] if v['path']!=target]
            report['files'].append({'path':target,'bytes':size,'sha256':digest})
            journal.write_text(json.dumps(report,indent=2))
            print('Verified '+name,flush=True)
        sound=a.repo/'platform/super_s3_216/overrides/settings-sound.json'
        target='/littlefs/system/apps/brookesia.general.settings/res/screens/sound.json'
        apps=call('SystemCore','ListApps')
        candidates=['/littlefs/apps/brookesia.general.settings/res/screens/sound.json',target,'/littlefs/system/super/settings/res/screens/sound.json']
        for candidate in candidates:
            if call('Storage','FSStat',{'Path':candidate})['exists']:target=candidate;break
        else:raise RuntimeError('Settings sound resource path not found; inspect app package')
        call('Storage','FSCopyTree',{'From':target,'To':backup+'/settings-sound.json','Overwrite':False})
        done=c.transfer('put',sound,'offline-settings-update.bin',True);assert done['sha256']==hashlib.sha256(sound.read_bytes()).hexdigest()
        call('Storage','FSRename',{'From':'/littlefs/usb/offline-settings-update.bin','To':target})
        assert call('Storage','FSStat',{'Path':target})['size']==sound.stat().st_size
        # Update only the three changed book files; keep theme indexes and bookmarks.
        book=next(v for v in apps if v['manifest']['id']=='local.audiobook')
        if book['state'] in ('Running','Paused','Starting'):
            call('SystemCore','RequestCloseApp',{'AppId':book['app_id']});time.sleep(1)
        for name in ['manifest.json','app/main.js','res/screens/main.json']:
            local=a.repo/'brookesia-apps/audiobook/src'/name;target='/littlefs/apps/local.audiobook/'+name
            call('Storage','FSCopyTree',{'From':target,'To':backup+'/book-'+name.replace('/','-'),'Overwrite':False})
            done=c.transfer('put',local,'offline-book-update.bin',True)
            assert done['sha256']==hashlib.sha256(local.read_bytes()).hexdigest()
            call('Storage','FSRename',{'From':'/littlefs/usb/offline-book-update.bin','To':target})
            assert call('Storage','FSStat',{'Path':target})['size']==local.stat().st_size
        call('OfflineVoice','SetEnabled',{'Enabled':True})
        for _ in range(120):
            state=call('OfflineVoice','GetState')
            if state['active']:break
            time.sleep(.25)
        else:raise RuntimeError('Offline model did not start: '+json.dumps(state,ensure_ascii=False))
        report['state']=state;report['complete']=True;journal.write_text(json.dumps(report,indent=2))
        print(json.dumps(state,ensure_ascii=False),flush=True)
    print('Resources verified; restart once to reload Settings.',flush=True)
if __name__=='__main__':main()
