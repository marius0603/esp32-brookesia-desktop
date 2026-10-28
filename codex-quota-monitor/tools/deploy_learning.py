"""Install the learning apps, or merge a JSON content package into the SD library."""
import argparse,hashlib,json,re,struct,time,zipfile
from datetime import datetime
from pathlib import Path,PurePosixPath
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent

def install_app(port,package):
    for attempt in range(3):
        try:
            with StoryClient(port,timeout=30) as c:
                c.hello()
                assert c.transfer('install_bpk',package,None,False)['ok']
            return
        except RuntimeError as e:
            if attempt==2 or 'Wait timeout after 5000 ms' not in str(e):raise
            time.sleep(7)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--port',required=True)
    p.add_argument('--content',type=Path,default=REPO/'packages/content/learning-starter-1.3.0.zip')
    p.add_argument('--content-only',action='store_true')
    args=p.parse_args()
    stage=ROOT/'runtime'/('learning-install-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    stage.mkdir(parents=True)
    with zipfile.ZipFile(args.content) as z:
        assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
        manifest=json.loads(z.read('manifest.json'))
        assert manifest['schema']==1 and 1<=len(manifest['files'])<=1024
        for name,meta in manifest['files'].items():
            assert name in ('index.json','photo-sources.json','PHOTO-CREDITS.json','audio-sources.json') or re.fullmatch(r'packs/[a-z0-9][a-z0-9_-]{0,31}/[a-zA-Z0-9_./-]+',name),name
            assert '\\' not in name and all(part not in ('','.','..') for part in name.split('/')),name
            assert Path(name).suffix in ('.json','.wav','.png'),name
            data=z.read(name)
            assert len(data)==meta['bytes']<=512*1024 and hashlib.sha256(data).hexdigest()==meta['sha256'],name
            if name.endswith('.png'):
                assert data.startswith(b'\x89PNG\r\n\x1a\n') and len(data)>24
                w,h=struct.unpack('>II',data[16:24])
                assert 0<w<=256 and 0<h<=256,'Pack images must be at most 256x256'
            dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    incoming=json.loads((stage/'index.json').read_text(encoding='utf-8'))
    assert incoming['schema']==1 and incoming['packs']
    for entry in incoming['packs']:
        assert re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,31}',entry['id'])
        assert 'packs/'+entry['id']+'/pack.json' in manifest['files']
    backup='/sdcard/resource-backups/'+stage.name
    report={'passed':False,'backup':backup,'files':[],'content_only':args.content_only}
    def call(c,s,f,a=None):return c.call(s,f,a or {})['result']
    with StoryClient(args.port,timeout=30) as c:
        c.hello()
        assert not call(c,'DeviceModes','GetState')['screen_locked']
        report['tracks_before']=call(c,'Audiobook','List')['tracks']
        report['volume_before']=call(c,'AudioPlayback','GetVolume')
        for app in call(c,'SystemCore','ListApps'):
            if app['manifest']['id'] in ('local.lightlearning','local.childmode') and app['state'] in ('Running','Paused','Starting'):
                call(c,'SystemCore','StopApp',{'AppId':app['app_id']})
        call(c,'Storage','FSMkdir',{'Path':backup})
        old_index={'schema':1,'packs':[]}
        if call(c,'Storage','FSStat',{'Path':'/sdcard/learning/index.json'})['exists']:
            old_index=json.loads(call(c,'Storage','FSReadText',{'Path':'/sdcard/learning/index.json'}))
            call(c,'Storage','FSCopyTree',{'From':'/sdcard/learning/index.json','To':backup+'/index.json','Overwrite':False})
        for entry in incoming['packs']:
            target='/sdcard/learning/packs/'+entry['id']
            if call(c,'Storage','FSStat',{'Path':target})['exists']:
                call(c,'Storage','FSCopyTree',{'From':target,'To':backup+'/'+entry['id'],'Overwrite':False})
        for name in sorted(n for n in manifest['files'] if n!='index.json'):
            # FAT SD cards cannot rename a staged upload over an existing file.
            # Upload to a new path, verify it, then copy over the backed-up asset.
            staged=stage.name+'/'+name
            result=c.transfer('put',stage/name,'sd-learning/'+staged,False)
            assert result['ok'] and result['sha256']==manifest['files'][name]['sha256']
            report['files'].append(name)
        for name in report['files']:
            call(c,'Storage','FSCopyTree',{'From':'/sdcard/learning/'+stage.name+'/'+name,'To':'/sdcard/learning/'+name,'Overwrite':True})
        merged={e['id']:e for e in old_index['packs']}
        merged.update({e['id']:e for e in incoming['packs']})
        assert len(merged)<=16
        call(c,'Storage','FSWriteText',{'Path':'/sdcard/learning/index.json','Data':json.dumps({'schema':1,'packs':list(merged.values())},ensure_ascii=False)})
        assert re.fullmatch(r'learning-install-\d{8}-\d{6}',stage.name)
        call(c,'Storage','FSRemove',{'Path':'/sdcard/learning/'+stage.name})
        if not args.content_only:
            fonts_path='/littlefs/system/fonts/index.json'
            fonts=json.loads(call(c,'Storage','FSReadText',{'Path':fonts_path}))
            call(c,'Storage','FSCopyTree',{'From':fonts_path,'To':backup+'/fonts-index.json','Overwrite':False})
            font=REPO/'platform/super_s3_216/littlefs/system/fonts/learning-extra.ttf'
            assert c.transfer('put',font,'learning-extra.ttf',True)['ok']
            call(c,'Storage','FSRename',{'From':'/littlefs/usb/learning-extra.ttf','To':'/littlefs/system/fonts/learning-extra.ttf'})
            fonts['fonts']=[f for f in fonts['fonts'] if f['id']!='learning']
            fonts['fonts'].append({'id':'learning','kind':'file','src':'learning-extra.ttf','languages':['en','zh_CN'],'fallbacks':['${font.zh_CN}']})
            call(c,'Storage','FSWriteText',{'Path':fonts_path,'Data':json.dumps(fonts,ensure_ascii=False)})
            for app in call(c,'SystemCore','ListApps'):
                if app['manifest']['id']=='local.childmode':
                    call(c,'Storage','FSCopyTree',{'From':'/littlefs/apps/local.childmode','To':backup+'/child-app','Overwrite':False})
        assert call(c,'Audiobook','List')['tracks']==report['tracks_before']
        assert call(c,'AudioPlayback','GetVolume')==report['volume_before']
    if not args.content_only:
        for name in ('local.childmode.debug.0.1.1.bpk','local.lightlearning.debug.0.1.2.bpk'):
            install_app(args.port,REPO/'packages/apps'/name)
    report['passed']=True
    (ROOT/'runtime/learning-deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Learning content installed; reopen Light Learning.' if args.content_only else 'Learning package installed; stories and volume preserved. Restart once to load the font and launcher.')

if __name__=='__main__':main()
