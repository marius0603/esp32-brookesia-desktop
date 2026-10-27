"""Install the paired PC assistant without embedding cloud credentials."""
import argparse,contextlib,datetime,json,sys,time,zipfile
from pathlib import Path
from deploy_audiobook_sleep import StoryClient

ROOT=Path(__file__).resolve().parents[1]
VERSIONS=json.loads((ROOT.parent/'versions.json').read_text(encoding='utf-8'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--model-root',type=Path,required=True);a=p.parse_args()
    model_root=a.model_root.resolve();sys.path.insert(0,str(model_root/'scripts'))
    import config_store
    config=config_store.load();url=config.get('device_url','')
    if not url.startswith('wss://'):raise SystemExit('Configure an encrypted public device endpoint first')
    version=VERSIONS['apps']['local.voiceassistant']
    package=ROOT.parent/('packages/apps/local.voiceassistant.debug.'+version+'.bpk')
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        assert json.loads(z.read('manifest.json'))['package']['version']==version
        assert z.read('res/images/launcher_icon.png')==(ROOT.parent/'themes/cartoon-q-v1/flash-fallback/assistant.png').read_bytes()
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    report={'backup':'/sdcard/resource-backups/pc-voice-'+stamp,'complete':False}
    with StoryClient(a.port,timeout=25) as c:
        c.hello()
        def call(s,f,args=None):return c.call(s,f,args or {})['result']
        assert call('DeviceModes','GetState')['firmware_version']==VERSIONS['firmware']
        if call('Wifi','GetGeneralState')!='Connected':
            raise SystemExit('Connect the device to Wi-Fi before installing the PC assistant')
        before=call('Audiobook','List')['tracks']
        local=call('LocalVoice','GetState')
        if local['active']:
            call('LocalVoice','Disconnect')
            deadline=time.monotonic()+15
            while call('LocalVoice','GetState')['active']:
                if time.monotonic()>deadline:raise TimeoutError('Assistant did not release audio')
                time.sleep(.2)
        call('LocalVoice','SetConnection',{'Url':url,'Token':config['device_token']})
        app=next(x for x in call('SystemCore','ListApps') if x['manifest']['id']=='local.voiceassistant')
        call('Storage','FSCopyTree',{'From':'/littlefs/apps/local.voiceassistant','To':report['backup'],'Overwrite':False})
        call('SystemCore','StopApp',{'AppId':app['app_id']})
        log_path=ROOT/'runtime'/('pc-voice-install-'+stamp+'.log')
        with log_path.open('w',encoding='utf-8') as log,contextlib.redirect_stderr(log):
            installed=c.transfer('install_bpk',package,None,False)
        assert installed['ok'],installed
        call('Storage','FSWriteText',{'Path':'/littlefs/voice-assistant-backend.json','Data':'{"backend":"pc"}'})
        app=next(x for x in call('SystemCore','ListApps') if x['manifest']['id']=='local.voiceassistant')
        assert app['manifest']['version']==version
        call('SystemCore','StartApp',{'AppId':app['app_id']})
        deadline=time.monotonic()+100
        while True:
            active=call('SystemCore','GetActiveApp');local=call('LocalVoice','GetState')
            assert not active['last_error'],active
            if local['channel']:break
            if local['state']=='Error':raise RuntimeError(local['message'])
            if time.monotonic()>deadline:raise TimeoutError('Public device connection timed out')
            time.sleep(.4)
        assert before==call('Audiobook','List')['tracks']
        report.update(complete=True,active=active,local_voice=local,story_count=len(before))
        (ROOT/'runtime/pc-voice-app-deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    config=config_store.load();config['device_address_changed']=False;config_store.save(config)
    print('Assistant '+version+' running and connected over public WSS; Q icon and stories preserved.')

if __name__=='__main__':main()
