"""Back up and update the story UI, then transfer audio directly to SD (s3.20+)."""
import argparse,hashlib,json,time,zipfile
from datetime import datetime
from pathlib import Path
from deploy_wallpaper_shift import WallpaperClient
ROOT=Path(__file__).resolve().parents[1]
FILES=('app/main.js','res/screens/main.json','manifest.json')
class StoryClient(WallpaperClient):
    def read_json(self):
        value=super().read_json()
        if 'max_frame_payload' in value:value['max_frame_payload']=min(value['max_frame_payload'],1024)
        return value
def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--port',default='COM5');p.add_argument('--downloaded',type=Path,required=True);a=p.parse_args()
    bpk=a.repo/'packages/apps/local.audiobook.debug.0.2.0.bpk'
    folder=ROOT/'runtime'/('story-sleep-'+datetime.now().strftime('%Y%m%d-%H%M%S'));folder.mkdir(parents=True)
    with zipfile.ZipFile(bpk) as z:
        assert z.testzip() is None
        manifest=json.loads(z.read('manifest.json'));assert manifest['package']['id']=='local.audiobook' and manifest['package']['version']=='0.2.0'
        for n in FILES:(folder/Path(n).name).write_bytes(z.read(n))
    stories=[(a.repo/'samples/stories/01-小马和月亮灯-原创.mp3','01-xiaoma-yueliang.mp3'),(a.downloaded,'02-gudong.mp3')]
    sources=json.loads((a.repo/'samples/stories/sources.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(stories[0][0].read_bytes()).hexdigest()==sources['original']['sha256']
    assert hashlib.sha256(stories[1][0].read_bytes()).hexdigest()==sources['downloaded']['sha256']
    previous_file=ROOT/'runtime/story-sleep-deployment.json'
    previous=json.loads(previous_file.read_text()).get('stories',[]) if previous_file.exists() else []
    report={'backup':'/sdcard/resource-backups/'+folder.name,'stories':[],'restart_required':True}
    with StoryClient(a.port,timeout=20) as c:
        c.hello()
        def call(s,f,p=None):return c.call(s,f,p or {})['result']
        assert 'story_dim_per_mille' in call('DeviceModes','GetState'),'Flash s3.20 first'
        call('DeviceModes','Wake')
        app=next(x for x in call('SystemCore','ListApps') if x['manifest']['id']=='local.audiobook')
        if app['state'] in ('Running','Paused','Starting'):
            call('SystemCore','RequestCloseApp',{'AppId':app['app_id']});time.sleep(2)
        call('Storage','FSMkdir',{'Path':report['backup']})
        for n in FILES:
            target='/littlefs/apps/local.audiobook/'+n
            call('Storage','FSCopyTree',{'From':target,'To':report['backup']+'/'+Path(n).name,'Overwrite':False})
            done=c.transfer('put',folder/Path(n).name,'story-ui-update.bin',True);assert done['ok']
            call('Storage','FSRename',{'From':'/littlefs/usb/story-ui-update.bin','To':target})
            assert call('Storage','FSStat',{'Path':target})['size']==(folder/Path(n).name).stat().st_size
        for local,name in stories:
            call('DeviceModes','Wake')
            target='/sdcard/audiobooks/bedtime/'+name
            existing=call('Storage','FSStat',{'Path':target})
            if existing['exists']:
                digest=hashlib.sha256(local.read_bytes()).hexdigest()
                verified=next((v for v in previous if v['path']==target and v['sha256']==digest and v['bytes']==existing['size']==local.stat().st_size),None)
                if not verified:raise RuntimeError('Refusing to overwrite an unverified existing story: '+target)
                report['stories'].append(verified);print('Keeping previously hash-verified '+name,flush=True);continue
            print('Transferring '+name+' directly to SD',flush=True)
            done=c.transfer('put',local,'sd-audiobooks/bedtime/'+name,False)
            assert done['ok'] and done['sha256']==hashlib.sha256(local.read_bytes()).hexdigest()
            assert call('Storage','FSStat',{'Path':target})['size']==local.stat().st_size
            report['stories'].append({'path':target,'bytes':local.stat().st_size,'sha256':done['sha256']})
            (ROOT/'runtime/story-sleep-deployment.json').write_text(json.dumps(report,indent=2))
        assert json.loads(call('Storage','FSReadText',{'Path':'/littlefs/apps/local.audiobook/manifest.json'}))==manifest
    print('Story UI updated; both SD audio hashes verified. Restart to rediscover version 0.2.0.',flush=True)
if __name__=='__main__':main()
