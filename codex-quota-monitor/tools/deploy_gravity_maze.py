"""Verified SD-only maze install/update, retaining app data and the entire old tree."""
import hashlib,json,struct,time,zipfile
from pathlib import Path,PurePosixPath
from maintenance_client import SharedPowerDiagnosticClient
ROOT=Path(__file__).resolve().parents[2];BASE='/sdcard/apps/local.gravitymaze'
def tree_hash(files):
 h=hashlib.sha256()
 for n,b in sorted(files.items()):h.update(n.encode()+b'\0'+struct.pack('<Q',len(b))+b)
 return h.hexdigest()
def main():
 version=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps']['local.gravitymaze'];package=ROOT/f'packages/apps/local.gravitymaze.debug.{version}.bpk'
 with zipfile.ZipFile(package) as z:
  assert z.testzip() is None;files={n:z.read(n) for n in z.namelist()}
 assert json.loads(files['manifest.json'])['package']['id']=='local.gravitymaze'
 for n in files:assert not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts and '\\' not in n and not n.startswith('data/')
 stamp=str(time.time_ns());ready='/sdcard/resource-backups/maze-'+stamp+'-ready';check=ready+'-check';report_path=ROOT/'codex-quota-monitor/runtime/maze-deployment.json';prior=json.loads(report_path.read_text()) if report_path.exists() else {}
 report={'passed':False,'version':version,'resource_tree_sha256':tree_hash(files),'files':list(files),'package_sha256':hashlib.sha256(package.read_bytes()).hexdigest()}
 with SharedPowerDiagnosticClient('COM5',timeout=35) as c:
  c.hello()
  def f(s,n,a=None):return c.call_timeout(s,n,a or {})['result']
  assert f('DeviceModes','GetState')['firmware_version']==json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['firmware']
  for s in ['Audiobook','Radio','VoiceAssistant','LocalVoice']:assert not f(s,'GetState')['active'],'Finish other audio first'
  for a in f('SystemCore','ListApps'):
   if a['manifest']['id']=='local.gravitymaze':f('SystemCore','StopApp',{'AppId':a['app_id']})
  exists=f('Storage','FSStat',{'Path':BASE})['exists'];data_before=None
  if exists:
   assert prior.get('passed'),'No previous deployment record; inspect existing maze before updating'
   old_check=ready+'-old-check';f('Storage','FSMkdir',{'Path':old_check})
   for n in prior['files']:f('Storage','FSCopyTree',{'From':BASE+'/'+n,'To':old_check+'/'+n,'Overwrite':False})
   assert f('SdResources','InspectTree',{'Path':old_check})['sha256']==prior['resource_tree_sha256'],'Unknown source edits'
   if f('Storage','FSStat',{'Path':BASE+'/data'})['exists']:data_before=f('SdResources','InspectTree',{'Path':BASE+'/data'})['sha256']
   f('Storage','FSCopyTree',{'From':BASE,'To':ready,'Overwrite':False})
  else:f('Storage','FSMkdir',{'Path':ready})
  for number,(n,b) in enumerate(sorted(files.items(),key=lambda p:p[0]=='manifest.json')):
   local=ROOT/'codex-quota-monitor/runtime/maze-transfer.bin';local.write_bytes(b);name='maze-'+stamp+'.bin';r=c.transfer('put',local,'sd-themes/'+name,False);assert r['ok'] and r['sha256']==hashlib.sha256(b).hexdigest()
   f('Storage','FSCopyTree',{'From':'/sdcard/themes/'+name,'To':ready+'/'+n,'Overwrite':exists});f('Storage','FSRemove',{'Path':'/sdcard/themes/'+name})
  f('Storage','FSMkdir',{'Path':check})
  for n in files:f('Storage','FSCopyTree',{'From':ready+'/'+n,'To':check+'/'+n,'Overwrite':False})
  assert f('SdResources','InspectTree',{'Path':check})['sha256']==report['resource_tree_sha256']
  if data_before:assert f('SdResources','InspectTree',{'Path':ready+'/data'})['sha256']==data_before
  expected=f('SdResources','InspectTree',{'Path':ready})['sha256']
  retired=ready+'-previous'
  if exists:f('Storage','FSRename',{'From':BASE,'To':retired})
  try:f('Storage','FSRename',{'From':ready,'To':BASE})
  except BaseException:
   if exists:f('Storage','FSRename',{'From':retired,'To':BASE})
   raise
  assert f('SdResources','InspectTree',{'Path':BASE})['sha256']==expected
  report.update(passed=True,data_preserved=data_before is not None,previous=retired if exists else None,tree_sha256=expected)
 report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print('Maze SD resources verified; old tree and all app data retained. Restart to register app.')
if __name__=='__main__':main()
