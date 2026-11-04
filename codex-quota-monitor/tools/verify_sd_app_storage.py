"""Exercise the real installer with a disposable, hidden SD application.

The recovery phase leaves a realistic interrupted-install journal for the next
boot. It never alters a user's application. Run verify-recovery after a reset,
then cleanup. Do not use these diagnostic packages as application templates.
"""
import argparse
import io
import json
from pathlib import Path
import struct
import zipfile
from maintenance_client import MaintenanceClient

ROOT=Path(__file__).resolve().parents[1]
ID='local.storage.test'
BASE='/sdcard/apps/'+ID
BACKUP='/sdcard/apps/.rollback/'+ID
JOURNAL='/sdcard/apps/.transactions/'+ID+'.json'
STAGE='/sdcard/apps/.installing/'+ID+'-recovery-test'

def package(version,bad_gui=False,oversize=False,unsafe=False):
 manifest={'package':{'id':ID,'name':{'en':'Storage verification'},'version':version,'visible':False,'systems':['super']},
           'runtime':{'type':'JavaScript','entry':'app/main.js','resource_dir':'res','arguments':[]}}
 files={'manifest.json':json.dumps(manifest),'app/main.js':'''(function(){
function call(h,n,a){const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(a||{})));if(!r.success)throw new Error(r.error||n);return r.data;}
globalThis.brookesia_app={on_start(){const h=brookesia.start_service('SystemCore');const paths=call(h,'GetAppStoragePaths');if(paths.internal.available)throw new Error('Optional app must not use Flash private storage');call(h,'StorageWrite',{Location:{kind:'AppData',relative_path:'routing-check.json'},Data:JSON.stringify(paths)});return true;},on_stop(){return true;}};
})();''',
        'res/profile.json':json.dumps({'root':'root.json','preload_dom':bad_gui,'screen_flows':[{'screen_flow':'main','layer':'AppDefault'}]}),
        'res/root.json':json.dumps({'version':'0.1.1','assets':['screens/main.json','flows/main.json']}),
        'res/screens/main.json':'{' if bad_gui else json.dumps({'type':'viewScreen','id':'main','children':[]}),
        'res/flows/main.json':json.dumps({'type':'screenFlow','id':'main','screens':['main'],'initial':'main'})}
 if unsafe:files['../escape.txt']='reject this path'
 if oversize:
  # Small adversarial archive declaring 128 GiB. Preflight must reject it
  # without allocating, expanding or filling the card.
  files.update({'large-'+str(i)+'.bin':'' for i in range(64)})
 stream=io.BytesIO()
 with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
  for name,text in files.items():z.writestr(name,text)
 data=bytearray(stream.getvalue())
 if oversize:
  at=0
  while True:
   at=data.find(b'PK\x01\x02',at)
   if at<0:break
   length=struct.unpack_from('<H',data,at+28)[0]
   name=data[at+46:at+46+length].decode()
   if name.startswith('large-'):struct.pack_into('<I',data,at+24,0x80000000)
   at+=46+length
 return bytes(data)

def main():
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM5')
 p.add_argument('--phase',choices=['install','prepare-recovery','verify-recovery','prepare-cross-recovery','verify-cross-recovery','cleanup'],default='install')
 p.add_argument('--restart-fixture',action='store_true',help='Replace only this tool-owned diagnostic app after an interrupted test')
 a=p.parse_args();folder=ROOT/'runtime/sd-storage-check';folder.mkdir(parents=True,exist_ok=True)
 report_path=folder/'report.json'
 report=json.loads(report_path.read_text()) if report_path.exists() else {}
 def save():report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 with MaintenanceClient(a.port,timeout=20) as c:
  c.hello()
  def f(s,n,v=None):return c.call_timeout(s,n,v or {})['result']
  def storage(n,v):return f('Storage',n,v)
  def apps():return {x['id']:x for x in f('SystemCore','AppStorageInfo')['apps']}
  def digest():return f('SdResources','InspectTree',{'Path':BASE})
  def install(version,**kwargs):
   path=folder/('fixture-'+version+'.bpk');path.write_bytes(package(version,**kwargs))
   return c.transfer('install_bpk',path,None,True)
  if a.phase=='install':
   if ID in apps() or storage('FSStat',{'Path':BASE})['exists']:
    assert a.restart_fixture and report.get('fixture')==ID and apps()[ID]['path']==BASE,'Refuse existing diagnostic app without matching ownership record'
   assert not storage('FSStat',{'Path':JOURNAL})['exists']
   report={'fixture':ID,'passed':False};save()
   install('1.0.0')
   assert apps()[ID]['path']==BASE
   storage('FSWriteText',{'Path':BASE+'/data/keep.txt','Data':'preserved private data'})
   f('SystemCore','StartApp',{'AppId':apps()[ID]['app_id']})
   f('SystemCore','StopApp',{'AppId':apps()[ID]['app_id']})
   routed=json.loads(storage('FSReadText',{'Path':BASE+'/data/routing-check.json'}))
   assert not routed['internal']['available'] and any(v['available'] for v in routed['external'])
   report['sd_private_routing']=True
   before=digest();report['original']=before;save()
   for label,options,message in [('space',{'oversize':True},'Insufficient install space'),('path',{'unsafe':True},'Unsafe path'),('rollback',{'bad_gui':True},None)]:
    try:install('1.0.1',**options)
    except RuntimeError as e:
     if message:assert message in str(e),str(e)
     report[label+'_error']=str(e)
    else:raise AssertionError(label+' should fail')
    assert apps()[ID]['version']=='1.0.0' and digest()==before,label
    assert not storage('FSStat',{'Path':JOURNAL})['exists'],label
    save()
   install('1.0.1')
   assert apps()[ID]['version']=='1.0.1'
   assert storage('FSReadText',{'Path':BASE+'/data/keep.txt'})=='preserved private data'
   assert f('SdResources','InspectTree',{'Path':BACKUP})==before
   assert not storage('FSStat',{'Path':JOURNAL})['exists']
   report['passed']=True;save()
  elif a.phase=='prepare-recovery':
   assert report.get('passed') and apps()[ID]['version']=='1.0.1'
   assert f('SdResources','InspectTree',{'Path':BACKUP})==report['original']
   assert not storage('FSStat',{'Path':JOURNAL})['exists']
   storage('FSMkdir',{'Path':STAGE})
   storage('FSWriteText',{'Path':JOURNAL,'Data':json.dumps({'schema':1,'id':ID,'nonce':'recovery-test','old':BASE,'final':BASE,'backup':BACKUP,'stage':STAGE})})
   report['recovery_prepared']=True;save()
   print('Interrupted-commit fixture prepared; reset device before verify-recovery.')
  elif a.phase=='verify-recovery':
   assert report.get('recovery_prepared')
   assert apps()[ID]['version']=='1.0.0' and digest()==report['original']
   assert not storage('FSStat',{'Path':JOURNAL})['exists']
   assert not storage('FSStat',{'Path':STAGE})['exists']
   report['recovery_passed']=True;save()
  elif a.phase=='prepare-cross-recovery':
   assert report.get('passed') and apps()[ID]['version']=='1.0.1'
   assert f('SdResources','InspectTree',{'Path':BACKUP})==report['original']
   assert not storage('FSStat',{'Path':JOURNAL})['exists']
   old='/littlefs/apps/'+ID
   # Only this tool's private ownership record permits replacing its fixture.
   assert report.get('fixture')==ID
   if storage('FSStat',{'Path':old})['exists']:storage('FSRemove',{'Path':old})
   storage('FSMkdir',{'Path':old})
   storage('FSWriteText',{'Path':old+'/partial.txt','Data':'interrupted restore'})
   storage('FSMkdir',{'Path':STAGE})
   nonce='cross-recovery-test'
   storage('FSWriteText',{'Path':JOURNAL,'Data':json.dumps({'schema':1,'id':ID,'nonce':nonce,'old':old,'final':BASE,'backup':BACKUP,'stage':STAGE})})
   storage('FSWriteText',{'Path':JOURNAL.removesuffix('.json')+'.restoring','Data':json.dumps({'nonce':nonce})})
   report['cross_recovery_prepared']=True;save()
   print('Partial cross-volume restore fixture prepared; reset before verify-cross-recovery.')
  elif a.phase=='verify-cross-recovery':
   assert report.get('cross_recovery_prepared')
   old='/littlefs/apps/'+ID
   assert apps()[ID]['version']=='1.0.0' and apps()[ID]['path']==old
   assert f('SdResources','InspectTree',{'Path':old})==report['original']
   for path in (BASE+'/manifest.json',STAGE,JOURNAL,JOURNAL.removesuffix('.json')+'.restoring'):
    assert not storage('FSStat',{'Path':path})['exists'],path
   report['cross_recovery_passed']=True;save()
  else:
   assert report.get('fixture')==ID,'No private ownership record'
   if ID in apps():f('SystemCore','StopApp',{'AppId':apps()[ID]['app_id']})
   for path in (BASE,BACKUP,STAGE,JOURNAL,JOURNAL.removesuffix('.json')+'.committed',JOURNAL.removesuffix('.json')+'.restoring','/littlefs/apps/'+ID):
    if storage('FSStat',{'Path':path})['exists']:storage('FSRemove',{'Path':path})
   report['cleaned']=True;save()
   print('Diagnostic files removed; reset device to discard its in-memory registration.')
 print('SD storage verification phase:',a.phase,'passed',flush=True)

if __name__=='__main__':main()
