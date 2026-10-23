"""Apply the provided Q theme with SD originals and compact Flash fallbacks.

The legacy cream Flash paths are retained as a fixed runtime theme slot.
All replaced files are copied to an SD backup before replacement.
"""
import argparse,hashlib,json,time
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[1]
FLASH='/littlefs/themes/cream-handdrawn-v1'
SD='/sdcard/themes/cartoon-q-v1'
SHELL='/littlefs/system/super/shell'
def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--port',default='COM5');a=p.parse_args()
    theme=a.repo/'themes/cartoon-q-v1';manifest=json.loads((theme/'theme.json').read_text(encoding='utf-8'))
    fallback=json.loads((theme/'flash-fallback/manifest.json').read_text())['files']
    assert manifest['id']=='cartoon-q-v1' and len(manifest['icons'])==9
    for name,entry in manifest['files'].items():
        data=(theme/name).read_bytes();assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
    for name,entry in fallback.items():assert hashlib.sha256((theme/'flash-fallback'/name).read_bytes()).hexdigest()==entry['sha256']
    folder=ROOT/'runtime'/('cartoon-theme-'+datetime.now().strftime('%Y%m%d-%H%M%S'));folder.mkdir(parents=True)
    backup='/sdcard/resource-backups/'+folder.name
    report={'backup':backup,'files':[],'restart_required':True}
    with StoryClient(a.port,timeout=25) as c:
        c.hello()
        def call(s,f,p=None):return c.call(s,f,p or {})['result']
        def storage(f,p):return call('Storage',f,p)
        assert call('SdResources','GetState').get('theme')=='cartoon-q-v1','Flash s3.21 first'
        call('DeviceModes','Wake')
        for app in call('SystemCore','ListApps'):
            if app['manifest']['id']!='brookesia.system.super.shell' and app['state'] in ('Running','Paused','Starting'):
                call('SystemCore','RequestCloseApp',{'AppId':app['app_id']})
        time.sleep(1)
        storage('FSMkdir',{'Path':backup});storage('FSMkdir',{'Path':SD})
        def retain(path,name):
            before=storage('FSStat',{'Path':path})
            if before['exists']:
                storage('FSCopyTree',{'From':path,'To':backup+'/'+name,'Overwrite':False})
                assert storage('FSStat',{'Path':backup+'/'+name})['size']==before['size']
        def stage(source):
            done=c.transfer('put',source,'cartoon-theme-update.bin',True)
            assert done['sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
            return '/littlefs/usb/cartoon-theme-update.bin'
        capacity=storage('GetFileSystemCapacity',{'MountPoint':'/littlefs'})
        assert capacity['free_bytes']>=160000,capacity
        for name in manifest['files']:
            call('DeviceModes','Wake')
            retain(FLASH+'/'+name,'flash-'+name);retain(SD+'/'+name,'sd-'+name)
            staged=stage(theme/name)
            storage('FSCopyTree',{'From':staged,'To':SD+'/'+name,'Overwrite':True})
            assert storage('FSStat',{'Path':SD+'/'+name})['size']==manifest['files'][name]['bytes']
            if name in fallback:
                storage('FSRemove',{'Path':staged});staged=stage(theme/'flash-fallback'/name)
            storage('FSRename',{'From':staged,'To':FLASH+'/'+name})
            expected=fallback.get(name,manifest['files'][name])['bytes']
            assert storage('FSStat',{'Path':FLASH+'/'+name})['size']==expected
            report['files'].append(name);print('Updated Q theme '+name,flush=True)
        def update_json(target,value,name):
            retain(target,name);local=folder/name;local.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
            storage('FSRename',{'From':stage(local),'To':target})
            assert json.loads(storage('FSReadText',{'Path':target}))==value
        for app,name in manifest['icons'].items():
            target='/littlefs/apps/'+app+'/res/images/index.json'
            value=json.loads(storage('FSReadText',{'Path':target}))
            icon=next(i for i in value['images'] if i['id']=='launcher_icon')
            icon.update(src=FLASH+'/'+name,width=96,height=96)
            update_json(target,value,app+'-images.json')
        target=SHELL+'/styles/cream.json';value=json.loads(storage('FSReadText',{'Path':target}))
        styles=value['styles']
        styles['shell.launcherAppLabel']['textColor']='#fff2da'
        for key in ('shell.statusBrand','shell.statusTitle','shell.statusTiny'):
            if key in styles:styles[key]['textColor']='#fff2da'
        if 'shell.statusTinyMuted' in styles:styles['shell.statusTinyMuted']['textColor']='#d7e3fa'
        if 'shell.statusBar' in styles:styles['shell.statusBar'].update(bgColor='#3d527b',borderColor='#657c9e')
        update_json(target,value,'shell-styles.json')
        target=SHELL+'/screens/background.json';value=json.loads(storage('FSReadText',{'Path':target}))
        value['style']['bgColor']='#425b82';update_json(target,value,'shell-background.json')
        result=call('SdResources','GetState');assert all(f['exists'] and f['on_sd'] for f in result['files']),result
        report.update(complete=True,resource_state=result,capacity_after=storage('GetFileSystemCapacity',{'MountPoint':'/littlefs'}))
    (ROOT/'runtime/cartoon-theme-deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Nine Q icons and wallpaper deployed with compact Flash fallbacks; restart required.',flush=True)
if __name__=='__main__':main()
