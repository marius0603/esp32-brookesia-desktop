"""Move installed optional apps, retaining byte-verified SD rollback copies.

Run only with s3.46+, an inserted SD card and idle audio. Reports are private
because they include local paths and playback progress. Existing destination
trees are preserved in resource-backups rather than overwritten.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
from maintenance_client import MaintenanceClient

ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--port',default='COM5')
 p.add_argument('--report',type=Path,default=ROOT/'runtime/app-storage-migration.json')
 a=p.parse_args()
 assert a.report.resolve().is_relative_to((ROOT/'runtime').resolve()),'Keep device reports in private runtime'
 if a.report.exists():
  history=a.report.with_name(a.report.stem+'-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
  assert not history.exists()
  history.write_bytes(a.report.read_bytes())
 report={'passed':False,'migrations':[],'shadow_backups':[]}
 def save():
  a.report.parent.mkdir(parents=True,exist_ok=True)
  a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 with MaintenanceClient(a.port,timeout=40) as c:
  c.hello()
  def f(s,n,v=None):return c.call_timeout(s,n,v or {},180000 if n=='MigrateToSd' else 60000)['result']
  def inventory():return {x['id']:x for x in f('SystemCore','AppStorageInfo')['apps']}
  def tree(path):return f('SdResources','InspectTree',{'Path':path})
  mode=f('DeviceModes','GetState')
  assert mode['firmware_version'] in ('0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49')
  assert not mode['screen_locked'],'Unlock on the device before maintenance'
  before_audio={s:f(s,'GetState') for s in ('Audiobook','Radio','VoiceAssistant')}
  assert all(not s['active'] for s in before_audio.values()),'Finish active audio before migration'
  report.update(before=inventory(),playback_before=before_audio['Audiobook'],auto_deep_sleep_minutes=mode['auto_deep_sleep_minutes'])
  # Snapshot the catalogue, including file sizes, independently of app relocation.
  report['stories_before']=f('Storage','FSList',{'Path':'/sdcard/audiobooks/bedtime'})
  report['capacity_before']={m:f('Storage','GetFileSystemCapacity',{'MountPoint':m}) for m in ('/littlefs','/sdcard')}
  save()
  f('DeviceModes','Wake')
  f('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
  try:
   for app in f('SystemCore','ListApps'):
    if app['manifest']['id']!='brookesia.system.super.shell' and app['state'] in ('Running','Paused'):
     f('SystemCore','StopApp',{'AppId':app['app_id']})
   targets=[x for x in report['before'].values() if x['runtime'] and x['requires_sd'] and x['path'].startswith('/littlefs/apps/')]
   backup_root='/sdcard/resource-backups/pre-sd-migration-'+datetime.now().strftime('%Y%m%d-%H%M%S')
   for old in targets:
    name=old['id']
    assert '/' not in name and '\\' not in name and not name.startswith('.')
    source=tree(old['path'])
    destination='/sdcard/apps/'+name
    if f('Storage','FSStat',{'Path':destination})['exists']:
     shadow=tree(destination)
     f('Storage','FSMkdir',{'Path':backup_root})
     preserved=backup_root+'/'+name+'-shadow'
     f('Storage','FSRename',{'From':destination,'To':preserved})
     assert tree(preserved)==shadow
     report['shadow_backups'].append({'from':destination,'to':preserved,**shadow});save()
    current=inventory()[name]
    print('Migrating',name,source['bytes'],'bytes',flush=True)
    report['pending']={'id':name,'source':source};save()
    f('SystemCore','MigrateToSd',{'AppId':current['app_id']})
    after=inventory()[name]
    assert after['path']==destination and after['version']==old['version'],after
    installed=tree(destination);rollback=tree('/sdcard/apps/.rollback/'+name)
    assert installed==source and rollback==source,(name,source,installed,rollback)
    assert not f('Storage','FSStat',{'Path':old['path']})['exists']
    report['migrations'].append({'id':name,'from':old['path'],'to':destination,'verified':source});report.pop('pending',None);save()
   report['after']=inventory()
   assert set(report['after'])==set(report['before'])
   for name,app in report['after'].items():
    assert app['version']==report['before'][name]['version']
    if app['runtime'] and app['requires_sd']:assert app['path'].startswith('/sdcard/apps/'),app
    if not app['requires_sd'] and app['runtime']:assert app['path'].startswith('/littlefs/'),app
   report['stories_after']=f('Storage','FSList',{'Path':'/sdcard/audiobooks/bedtime'})
   assert report['stories_after']==report['stories_before'],'Story catalogue changed'
   report['capacity_after']={m:f('Storage','GetFileSystemCapacity',{'MountPoint':m}) for m in ('/littlefs','/sdcard')}
   report['passed']=True
  finally:
   f('DeviceModes','SetAutoDeepSleep',{'Minutes':mode['auto_deep_sleep_minutes']});save()
 print('Migration verified; foundation remains in Flash. Restart to verify SD rediscovery.',flush=True)

if __name__=='__main__':main()
