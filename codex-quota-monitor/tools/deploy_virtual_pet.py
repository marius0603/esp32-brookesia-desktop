"""Install the pet BPK and hash-verified SD frames, preserving existing device data."""
import argparse,hashlib,json,re,time,zipfile
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'brookesia-apps/virtual-pet'
IMAGE_INDEX='/littlefs/system/super/shell/images/index.json'
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);a=p.parse_args()
 content=APP/'content';manifest=json.loads((content/'manifest.json').read_text(encoding='utf-8'))
 for name,meta in manifest['files'].items():
  assert re.fullmatch(r'(frames/)?[a-z0-9_-]+\.(bin|json)',name),name
  data=(content/name).read_bytes();assert len(data)==meta['bytes'] and hashlib.sha256(data).hexdigest()==meta['sha256']
 stamp=datetime.now().strftime('%Y%m%d-%H%M%S');stage='virtual-pet-'+stamp
 folder=ROOT/'codex-quota-monitor/runtime'/stage;folder.mkdir(parents=True)
 backup='/sdcard/resource-backups/'+stage;report={'passed':False,'backup':backup,'uploaded':[]}
 version=json.loads((APP/'src/manifest.json').read_text(encoding='utf-8'))['package']['version']
 package=ROOT/('packages/apps/local.virtualpet.debug.'+version+'.bpk')
 with StoryClient(a.port,timeout=40) as c:
  c.hello()
  def f(s,n,args=None):return c.call(s,n,args or {})['result']
  def storage(n,args):return f('Storage',n,args)
  modes=f('DeviceModes','GetState');assert not modes['screen_locked'],'Unlock with double volume+ before installing'
  assert not f('Audiobook','GetState')['sleep_active'],'Let the active story sleep timer finish first'
  f('DeviceModes','Wake')
  report.update(volume=f('AudioPlayback','GetVolume'),tracks=f('Audiobook','List')['tracks'],theme=modes['desktop_theme_index'],apps=[x['manifest']['id'] for x in f('SystemCore','ListApps')])
  report['preferences']={}
  for path in ('/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json'):
   report['preferences'][path]=storage('FSReadText',{'Path':path}) if storage('FSStat',{'Path':path})['exists'] else None
  original=storage('FSReadText',{'Path':IMAGE_INDEX});(folder/'shell-images-before.json').write_text(original,encoding='utf-8')
  (folder/'preservation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  storage('FSMkdir',{'Path':backup});storage('FSCopyTree',{'From':IMAGE_INDEX,'To':backup+'/shell-images.json','Overwrite':False})
  target='/sdcard/pets/xiaoli'
  if storage('FSStat',{'Path':target})['exists']:storage('FSCopyTree',{'From':target,'To':backup+'/pet-content','Overwrite':False})
  app=next((x for x in f('SystemCore','ListApps') if x['manifest']['id']=='local.virtualpet'),None)
  if app:
   if app['state'] in ('Running','Paused','Starting'):f('SystemCore','StopApp',{'AppId':app['app_id']})
   old_path='/sdcard/apps/local.virtualpet'
   if not storage('FSStat',{'Path':old_path})['exists']:old_path='/littlefs/apps/local.virtualpet'
   storage('FSCopyTree',{'From':old_path,'To':backup+'/app','Overwrite':False})
  def upload(local,remote):
   staged=stage+'/'+str(len(report['uploaded']))+'-'+local.name
   result=c.transfer('put',local,'sd-themes/'+staged,False)
   assert result['ok'] and result['sha256']==hashlib.sha256(local.read_bytes()).hexdigest()
   storage('FSCopyTree',{'From':'/sdcard/themes/'+staged,'To':remote,'Overwrite':True})
   assert storage('FSStat',{'Path':remote})['size']==local.stat().st_size
   report['uploaded'].append(remote)
  for name in manifest['files']:
   # Keep a user-edited schedule on upgrades.
   if name=='schedule.json' and storage('FSStat',{'Path':target+'/'+name})['exists']:continue
   upload(content/name,target+'/'+name)
  upload(content/'manifest.json',target+'/manifest.json')
  images=json.loads(original);images['images']=[i for i in images['images'] if i['id']!='cyber.local.virtualpet']
  images['images'].append({'id':'cyber.local.virtualpet','src':target+'/launcher.bin','width':92,'height':92,'preload':True})
  local=folder/'shell-images.json';local.write_text(json.dumps(images,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8');upload(local,IMAGE_INDEX)
  assert json.loads(storage('FSReadText',{'Path':IMAGE_INDEX}))==images
  layout=f('SystemCore','GetStorageLayout');report['storage_layout_before']=layout
  # The installer supports External storage; use it for this app, then restore policy.
  f('SystemCore','SetDefaultInstallStorage',{'Target':'External'})
  try:
   assert storage('GetFileSystemCapacity',{'MountPoint':'/littlefs'})['free_bytes']>=package.stat().st_size+32768
   result=c.transfer('install_bpk',package,None,False);assert result['ok']
  finally:
   f('SystemCore','SetDefaultInstallStorage',{'Target':layout['default_install_target'],'PreferredExternalId':layout.get('preferred_external_id','')})
  pet=next(x for x in f('SystemCore','ListApps') if x['manifest']['id']=='local.virtualpet')
  assert pet['manifest']['version']==version
  report['installed_app']=pet
  for path,old in report['preferences'].items():
   if old is not None:assert storage('FSReadText',{'Path':path})==old
  assert f('AudioPlayback','GetVolume')==report['volume'] and f('Audiobook','List')['tracks']==report['tracks']
  assert f('DeviceModes','GetState')['desktop_theme_index']==report['theme']
  assert re.fullmatch(r'virtual-pet-\d{8}-\d{6}',stage)
  storage('FSRemove',{'Path':'/sdcard/themes/'+stage})
  report['passed']=True
  (folder/'deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  (ROOT/'codex-quota-monitor/runtime/virtual-pet-latest.json').write_text(json.dumps({'folder':str(folder)}),encoding='utf-8')
 print('Pet app and native SD frames installed; existing stories, volume, theme and preferences preserved. Restart once to reload desktop resources.')
if __name__=='__main__':main()
