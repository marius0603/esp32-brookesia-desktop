"""Install transparent native Q icons on SD, backing up every app image index."""
import argparse,hashlib,json,time
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[2]

def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--restore',type=Path);a=p.parse_args()
 source=ROOT/'themes/cartoon-q-v1/launcher-optimized'
 manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
 assert manifest['transparent'] and manifest['format']=='LVGL RGB565A8 RLE'
 for n,m in manifest['files'].items():assert hashlib.sha256((source/n).read_bytes()).hexdigest()==m['sha256']
 stamp=datetime.now().strftime('%Y%m%d-%H%M%S');folder=ROOT/'codex-quota-monitor/runtime'/('transparent-icons-'+stamp);folder.mkdir()
 report={'passed':False,'backup':'/sdcard/resource-backups/transparent-icons-'+stamp,'files':[]}
 with StoryClient(a.port,timeout=30) as c:
  c.hello()
  def f(s,n,p=None):return c.call(s,n,p or {})['result']
  def storage(n,p):return f('Storage',n,p)
  if a.restore:
   originals=json.loads((a.restore/'original-resources.json').read_text(encoding='utf-8'))
   for path,text in originals.items():
    storage('FSWriteText',{'Path':path,'Data':text});assert storage('FSReadText',{'Path':path})==text
   print('Restored original icon indexes; restart to reload.');return
  state=f('Audiobook','GetState');modes=f('DeviceModes','GetState')
  version=modes.get('firmware_version','').split('-s3.')
  assert len(version)==2 and version[-1].isdigit() and int(version[-1])>=41,'Install s3.41 RGB565A8 loader support before these icon resources'
  assert not state['sleep_active'] and not modes['screen_locked'],'Cancel sleep timer and unlock before an update requiring restart'
  voice=f('VoiceAssistant','GetState');assert not voice.get('recording',False),'Finish the assistant conversation before restarting'
  apps=f('SystemCore','ListApps');tracks=f('Audiobook','List')['tracks'];volume=f('AudioPlayback','GetVolume')
  originals={};indexes={}
  for app in apps:
   appid=app['manifest']['id']
   if appid not in manifest['icons']:continue
   relative='/apps/'+appid+'/res/images/index.json';path='/littlefs'+relative
   if not storage('FSStat',{'Path':path})['exists']:path='/sdcard'+relative
   text=storage('FSReadText',{'Path':path});originals[path]=text;indexes[appid]=(path,json.loads(text))
  assert set(indexes)==set(manifest['icons']),'Wait for all apps to load'
  (folder/'original-resources.json').write_text(json.dumps(originals,ensure_ascii=False,indent=2),encoding='utf-8')
  (folder/'preservation.json').write_text(json.dumps({'story':state,'modes':modes,'volume':volume,'tracks':tracks},ensure_ascii=False),encoding='utf-8')
  storage('FSMkdir',{'Path':report['backup']})
  for i,(path,text) in enumerate(originals.items()):storage('FSWriteText',{'Path':report['backup']+'/'+str(i)+'.json','Data':text})
  try:
   for appid,(path,doc) in indexes.items():
    name=manifest['icons'][appid];meta=manifest['files'][name]
    relative='launcher-alpha-v1-'+stamp+'/'+appid+'-'+meta['sha256'][:12]+'.bin'
    dest='sd-themes/'+relative
    result=c.transfer('put',source/name,dest,False);assert result['ok'] and result['sha256']==meta['sha256']
    remote='/sdcard/themes/'+relative
    icon=next(x for x in doc['images'] if x['id']=='launcher_icon')
    icon.update(src=remote,width=92,height=92,preload=True)
    storage('FSWriteText',{'Path':path,'Data':json.dumps(doc,ensure_ascii=False,separators=(',',':'))})
    assert json.loads(storage('FSReadText',{'Path':path}))==doc
    report['files'].append({'app':appid,'path':remote,'sha256':meta['sha256']})
   assert f('Audiobook','List')['tracks']==tracks and f('AudioPlayback','GetVolume')==volume
   report['passed']=True
  except Exception:
   for path,text in originals.items():storage('FSWriteText',{'Path':path,'Data':text})
   raise
 (folder/'deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 (ROOT/'codex-quota-monitor/runtime/transparent-icons-latest.json').write_text(json.dumps({'folder':str(folder)}),encoding='utf-8')
 print('Verified transparent indexes for',len(report['files']),'apps. Restart to reload. Backup:',folder)

if __name__=='__main__':main()
