"""Install reversible desktop artwork and Settings resources on s3.31."""
import argparse,hashlib,json,re,time
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
from desktop_theme_resources import update_display,update_button,update_launcher,cyber_images
ROOT=Path(__file__).resolve().parents[2]
def main():
    p=argparse.ArgumentParser();p.add_argument('--port',required=True);args=p.parse_args()
    source=ROOT/'themes/cyberpunk-v1';manifest=json.loads((source/'theme.json').read_text(encoding='utf-8'))
    assert manifest['schema']==1 and len(manifest['icons'])==10
    for name,meta in manifest['files'].items():
        assert re.fullmatch(r'[a-z0-9_.-]+\.bin',name)
        data=(source/name).read_bytes();assert len(data)==meta['bytes'] and hashlib.sha256(data).hexdigest()==meta['sha256']
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S');folder=ROOT/'codex-quota-monitor/runtime'/('desktop-theme-install-'+stamp);folder.mkdir()
    stage='desktop-theme-'+stamp;backup='/sdcard/resource-backups/'+stage
    with StoryClient(args.port,timeout=40) as c:
        c.hello()
        def f(s,n,a=None):return c.call(s,n,a or {})['result']
        def storage(n,a):return f('Storage',n,a)
        deadline=time.monotonic()+60
        while True:
            apps=f('SystemCore','ListApps')
            if any(a['app_id']==1 and a['state']=='Running' for a in apps) and set(manifest['icons']).issubset(a['manifest']['id'] for a in apps):break
            assert time.monotonic()<deadline,'Wait for the desktop and all apps to finish starting'
            time.sleep(1)
        modes=f('DeviceModes','GetState')
        assert modes['firmware_version']=='0.8.3-s3.31','Install s3.31 before transferring desktop resources'
        assert not modes['screen_locked'],'Unlock with double volume+ before updating'
        assert not f('Audiobook','GetState')['sleep_active'],'Wait for the sleep timer before installing'
        assert storage('GetFileSystemCapacity',{'MountPoint':'/littlefs'})['free_bytes']>=32768
        report={'passed':False,'tracks':f('Audiobook','List')['tracks'],'volume':f('AudioPlayback','GetVolume'),'backup':backup,'files':[]}
        for path in ('/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json'):
            report[path]=storage('FSReadText',{'Path':path}) if storage('FSStat',{'Path':path})['exists'] else None
        originals={}
        shell='/littlefs/system/super/shell/'
        settings='/littlefs/apps/brookesia.general.settings/res/screens/display.json'
        assert storage('FSStat',{'Path':settings})['exists']
        paths=[shell+'images/index.json',shell+'templates/launcher_app_button.json',shell+'screens/app_launcher.json',shell+'screens/background.json',settings,'/littlefs/system/fonts/index.json']
        for path in paths:originals[path]=storage('FSReadText',{'Path':path})
        (folder/'original-resources.json').write_text(json.dumps(originals,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (folder/'preservation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        storage('FSMkdir',{'Path':backup})
        for i,path in enumerate(paths):storage('FSCopyTree',{'From':path,'To':backup+'/'+str(i)+'.json','Overwrite':False})
        def upload(local,target):
            remote=stage+'/'+str(len(report['files']))+'-'+local.name
            result=c.transfer('put',local,'sd-themes/'+remote,False)
            assert result['ok'] and result['sha256']==hashlib.sha256(local.read_bytes()).hexdigest()
            storage('FSCopyTree',{'From':'/sdcard/themes/'+remote,'To':target,'Overwrite':True})
            assert storage('FSStat',{'Path':target})['size']==local.stat().st_size
            report['files'].append(target)
        for name in manifest['files']:upload(source/name,'/sdcard/themes/cyberpunk-v1/'+name)
        upload(source/'theme.json','/sdcard/themes/cyberpunk-v1/theme.json')
        font=ROOT/'platform/super_s3_216/littlefs/system/fonts/desktop-theme-extra.ttf';upload(font,'/littlefs/system/fonts/'+font.name)
        images=json.loads(originals[paths[0]]);images['images']=[i for i in images['images'] if not i['id'].startswith('cyber.')]+cyber_images(manifest)
        fonts=json.loads(originals[paths[-1]]);fonts['fonts']=[i for i in fonts['fonts'] if i['id']!='desktop_theme']
        fonts['fonts'].append({'id':'desktop_theme','kind':'file','src':font.name,'languages':['en','zh_CN'],'fallbacks':['${font.zh_CN}']})
        updates={paths[0]:images,paths[1]:update_button(json.loads(originals[paths[1]])),paths[2]:update_launcher(json.loads(originals[paths[2]])),settings:update_display(json.loads(originals[settings])),paths[-1]:fonts}
        # Upload larger documents through framed transfer instead of UART commands.
        for i,(path,doc) in enumerate(updates.items()):
            local=folder/('resource-'+str(i)+'.json');data=json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n';local.write_text(data,encoding='utf-8');upload(local,path)
            assert json.loads(storage('FSReadText',{'Path':path}))==doc,path
        assert f('Audiobook','List')['tracks']==report['tracks'] and f('AudioPlayback','GetVolume')==report['volume']
        for path in ('/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json'):
            if report[path] is not None:assert storage('FSReadText',{'Path':path})==report[path]
        assert storage('FSReadText',{'Path':paths[3]})==originals[paths[3]]
        assert re.fullmatch(r'desktop-theme-\d{8}-\d{6}',stage)
        storage('FSRemove',{'Path':'/sdcard/themes/'+stage})
        report['passed']=True;(folder/'deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (ROOT/'codex-quota-monitor/runtime/desktop-theme-latest.json').write_text(json.dumps({'folder':str(folder)}),encoding='utf-8')
        print('Desktop resources installed and read back; stories, bookmark, play mode and volume preserved. Restart to load resources, then select a desktop theme.')
if __name__=='__main__':main()
