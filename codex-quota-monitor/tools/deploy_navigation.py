"""Stage the new SD navigation app file by file, verify tree hash, publish atomically."""
import argparse,hashlib,json,struct,time,zipfile
from pathlib import Path,PurePosixPath
from maintenance_client import SharedPowerDiagnosticClient
ROOT=Path(__file__).resolve().parents[2]
BASE='/sdcard/apps/local.navigation'
def tree_hash(files):
 h=hashlib.sha256()
 for name,data in sorted(files.items()):h.update(name.encode()+b'\0'+struct.pack('<Q',len(data))+data)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM5');p.add_argument('--manifest-only',action='store_true',help='Clone known old tree and replace only manifest; require full target hash');p.add_argument('--text-only',action='store_true',help='Clone tree and replace JS/JSON; require full target hash');p.add_argument('--include',action='append',default=[],help='Additional archive file for a partial update');a=p.parse_args();partial=a.manifest_only or a.text_only
 version=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps']['local.navigation']
 package=ROOT/('packages/apps/local.navigation.debug.'+version+'.bpk')
 with zipfile.ZipFile(package) as z:
  assert z.testzip() is None;files={n:z.read(n) for n in z.namelist()}
 for name in files:
  n=PurePosixPath(name);assert not n.is_absolute() and '..' not in n.parts and '\\' not in name
 stamp=str(time.time_ns());ready='/sdcard/resource-backups/navigation-'+stamp+'-ready'
 previous=ROOT/'codex-quota-monitor/runtime/navigation-deployment.json'
 old_report=json.loads(previous.read_text(encoding='utf-8')) if previous.exists() else {}
 report={'passed':False,'tree_sha256':tree_hash(files),'package_sha256':hashlib.sha256(package.read_bytes()).hexdigest(),'ready':ready}
 with SharedPowerDiagnosticClient(a.port,timeout=35) as c:
  c.hello()
  def f(s,n,a=None):return c.call_timeout(s,n,a or {})['result']
  assert f('DeviceModes','GetState')['firmware_version']==json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['firmware']
  for s in ['Audiobook','Radio','VoiceAssistant','LocalVoice']:assert not f(s,'GetState')['active'],'Finish active audio first'
  apps=f('SystemCore','ListApps');report['other_apps']={x['manifest']['id']:x['manifest']['version'] for x in apps if x['manifest']['id']!='local.navigation'}
  exists=f('Storage','FSStat',{'Path':BASE})['exists']
  old=f('SdResources','InspectTree',{'Path':BASE}) if exists else None
  if exists and old['sha256']==report['tree_sha256']:
   report['already_installed']=True
  else:
   if exists:
    assert old_report.get('passed') and old['sha256']==old_report['tree_sha256'],'Unknown app edits; refusing update'
    for app in apps:
     if app['manifest']['id']=='local.navigation':f('SystemCore','StopApp',{'AppId':app['app_id']})
   if partial:
    assert exists,'Manifest-only update requires the complete old app'
    f('Storage','FSCopyTree',{'From':BASE,'To':ready,'Overwrite':False})
   else:f('Storage','FSMkdir',{'Path':ready})
   changed={n:d for n,d in files.items() if n.endswith(('.js','.json'))} if a.text_only else {'manifest.json':files['manifest.json']} if a.manifest_only else files
   for name in a.include:changed[name]=files[name]
   for i,(name,data) in enumerate(sorted(changed.items(),key=lambda p:(p[0]=='manifest.json',p[0]))):
    file=ROOT/'codex-quota-monitor/runtime/navigation-stage.bin';file.write_bytes(data);temp='nav-'+stamp+'.bin'
    r=c.transfer('put',file,'sd-themes/'+temp,False);assert r['ok'] and r['sha256']==hashlib.sha256(data).hexdigest()
    f('Storage','FSCopyTree',{'From':'/sdcard/themes/'+temp,'To':ready+'/'+name,'Overwrite':partial})
    f('Storage','FSRemove',{'Path':'/sdcard/themes/'+temp})
   assert f('SdResources','InspectTree',{'Path':ready})['sha256']==report['tree_sha256']
   if exists:
    retired=ready+'-previous';f('Storage','FSRename',{'From':BASE,'To':retired});report['previous']=retired
   try:f('Storage','FSRename',{'From':ready,'To':BASE})
   except BaseException:
    if exists:f('Storage','FSRename',{'From':retired,'To':BASE})
    raise
  assert f('SdResources','InspectTree',{'Path':BASE})['sha256']==report['tree_sha256']
  report['passed']=True
 (ROOT/'codex-quota-monitor/runtime/navigation-deployment.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print('Navigation SD tree hash verified; restart to register new app.')
if __name__=='__main__':main()
