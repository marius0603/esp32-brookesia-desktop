"""Install or restore the measured low-overhead launcher artwork and layout."""
import argparse,hashlib,json,time
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--restore',type=Path);p.add_argument('--solid-background',action='store_true',help='Optionally replace the wallpaper with the icon background color');a=p.parse_args()
source=ROOT.parent/'themes/cartoon-q-v1/launcher-optimized'
with StoryClient(a.port,timeout=40) as c:
 c.hello()
 def call(s,f,args=None):return c.call(s,f,args or {})['result']
 def storage(f,args):return call('Storage',f,args)
 if a.restore:
  original=json.loads((a.restore/'original-resources.json').read_text(encoding='utf-8'))
  for path,data in original.items():
   assert path.startswith(('/littlefs/apps/','/sdcard/apps/','/littlefs/system/super/shell/'))
   storage('FSWriteText',{'Path':path,'Data':json.dumps(json.loads(data),ensure_ascii=False,separators=(',',':'))})
  print('Original launcher resources restored. Restart once to reload app icons.');raise SystemExit(0)
 manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'));assert manifest['schema']==1 and manifest['size']==92
 for name,meta in manifest['files'].items():assert hashlib.sha256((source/name).read_bytes()).hexdigest()==meta['sha256']
 assert hashlib.sha256((source/manifest['layout']['file']).read_bytes()).hexdigest()==manifest['layout']['sha256']
 # Immutable filenames let repeated installs reuse the verified cache.
 base='/littlefs/themes/launcher-optimized-v1'
 pending=[]
 for appid,name in manifest['icons'].items():
  meta=manifest['files'][name];remote=base+'/'+appid+'-'+meta['sha256'][:12]+'.bin'
  if not storage('FSStat',{'Path':remote})['exists']:pending.append(meta)
 # Allow filesystem block rounding, transfer staging and metadata/GC room.
 needed=sum(((m['bytes']+4095)//4096)*4096 for m in pending)+max((m['bytes'] for m in pending),default=0)+65536
 assert storage('GetFileSystemCapacity',{'MountPoint':'/littlefs'})['free_bytes']>=needed,'Not enough free Flash for a safe cache install'
 folder=ROOT/'runtime'/('launcher-cache-'+datetime.now().strftime('%Y%m%d-%H%M%S'));folder.mkdir()
 apps=call('SystemCore','ListApps');volume=call('AudioPlayback','GetVolume');tracks=call('Audiobook','List')['tracks']
 originals={};images={}
 for app in apps:
  appid=app['manifest']['id']
  if appid not in manifest['icons']:continue
  relative='/apps/'+appid+'/res/images/index.json'
  path='/littlefs'+relative
  if not storage('FSStat',{'Path':path})['exists']:path='/sdcard'+relative
  text=storage('FSReadText',{'Path':path});originals[path]=text;images[appid]=(path,json.loads(text))
 for name in ('screens/background.json','screens/app_launcher.json'):
  path='/littlefs/system/super/shell/'+name;originals[path]=storage('FSReadText',{'Path':path})
 (folder/'original-resources.json').write_text(json.dumps(originals,ensure_ascii=False,indent=2),encoding='utf-8')
 storage('FSMkdir',{'Path':base})
 for appid,(path,doc) in images.items():
  name=manifest['icons'][appid];meta=manifest['files'][name];remote=base+'/'+appid+'-'+meta['sha256'][:12]+'.bin'
  if not storage('FSStat',{'Path':remote})['exists']:
   result=c.transfer('put',source/name,'launcher-cache-stage.bin',True);assert result['sha256']==meta['sha256']
   storage('FSRename',{'From':'/littlefs/usb/launcher-cache-stage.bin','To':remote})
  assert storage('FSStat',{'Path':remote})['size']==meta['bytes']
  icon=next(i for i in doc['images'] if i['id']=='launcher_icon');icon.update(src=remote,width=92,height=92)
 for appid,(path,doc) in images.items():storage('FSWriteText',{'Path':path,'Data':json.dumps(doc,ensure_ascii=False,separators=(',',':'))})
 changes={'/littlefs/system/super/shell/screens/app_launcher.json':(source/'app_launcher.json').read_text(encoding='utf-8')}
 if a.solid_background:
  background=json.loads(originals['/littlefs/system/super/shell/screens/background.json']);background['children']=[];background.setdefault('style',{}).update(bgColor=manifest['background'],bgOpacity=255)
  changes['/littlefs/system/super/shell/screens/background.json']=json.dumps(background,ensure_ascii=False,separators=(',',':'))
 for path,data in changes.items():
  storage('FSWriteText',{'Path':path,'Data':data});assert storage('FSReadText',{'Path':path})==data
 assert call('AudioPlayback','GetVolume')==volume and call('Audiobook','List')['tracks']==tracks
 report={'passed':True,'icons':len(images),'backup':str(folder),'volume':volume,'stories':len(tracks)}
 (folder/'deployment.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
 print('Restart once to reload the app icon catalog. Roll back with --restore '+str(folder))
