"""Exercise the largest map with temporary steering; restore release code and progress."""
import hashlib,json,time,zipfile
from pathlib import Path
from maintenance_client import SharedPowerDiagnosticClient
from deploy_gravity_maze import tree_hash
ROOT=Path(__file__).resolve().parents[2]
BASE='/sdcard/apps/local.gravitymaze'

def main():
 version=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps']['local.gravitymaze']
 with zipfile.ZipFile(ROOT/f'packages/apps/local.gravitymaze.debug.{version}.bpk') as z:release=z.read('app/main.js')
 source=release.decode('utf-8')
 # Aggregate on-device synchronous call times without extra per-frame I/O.
 needle="const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(a||{})));"
 assert source.count(needle)==1
 source='var mazeBench={};\n'+source.replace(needle,"const begin=Date.now();"+needle+"const ms=Date.now()-begin,p=mazeBench[n]||(mazeBench[n]={calls:0,ms:0,max:0});p.calls++;p.ms+=ms;p.max=Math.max(p.max,ms);")
 source=source.replace('const begin=Date.now();',"if(n==='SetBindings'&&a.Updates.some(u=>u.Path==='/main/viewport/world'&&(u.Key==='x'||u.Key==='y'))){const camera=mazeBench.CameraMoves||(mazeBench.CameraMoves={calls:0,ms:0,max:0});camera.calls++;}const begin=Date.now();")
 source=source.replace('Data:JSON.stringify({version:', 'Data:JSON.stringify({profile:mazeBench,version:')
 step='MazeCore.step(m,tilt.x,tilt.y,(now-lastTick)/1000);'
 assert source.count(step)==1
 source=source.replace(step,"const physicsBegin=Date.now();"+step+"const physicsMs=Date.now()-physicsBegin,physics=mazeBench.Physics||(mazeBench.Physics={calls:0,ms:0,max:0});physics.calls++;physics.ms+=physicsMs;physics.max=Math.max(physics.max,physicsMs);")
 assert source.count('on_timer(){tick();return true;},')==1 and source.count('const tilt=MazeCore.tilt(sample,base)')==1
 # Only this private temporary file drives real rendering/physics automatically.
 steering="""let testAt=1,testStarted=false;function testTilt(){
 const at=m.plan.route[Math.min(testAt,m.plan.route.length-1)],x=(at%m.n+.5)*m.cell,y=(Math.floor(at/m.n)+.5)*m.cell;
 if(Math.hypot(x-m.x,y-m.y)<3&&testAt<m.plan.route.length-1)testAt++;
 return {x:Math.max(-1,Math.min(1,(x-m.x)/25)),y:Math.max(-1,Math.min(1,(y-m.y)/25))};}
 function tick(){"""
 hook=source.replace('on_timer(){tick();return true;},',"on_timer(){tick();if(mode==='ready'&&!testStarted){testStarted=true;calibrate();}return true;},").replace('const tilt=MazeCore.tilt(sample,base)','const tilt=testTilt()').replace('function tick(){',steering)
 runtime=ROOT/'codex-quota-monitor/runtime';runtime.mkdir(exist_ok=True);stamp=str(time.time_ns())
 report={'passed':False,'version':version,'level':10,'synthetic_steering':True}
 with SharedPowerDiagnosticClient('COM5',timeout=35) as c:
  c.hello()
  def f(s,n,a=None):return c.call_timeout(s,n,a or {})['result']
  def upload(data,tag):
   file=runtime/('maze-load-'+tag+'.js');file.write_bytes(data);name='maze-load-'+stamp+'-'+tag+'.bin'
   r=c.transfer('put',file,'sd-themes/'+name,False);assert r['ok'] and r['sha256']==hashlib.sha256(data).hexdigest()
   f('Storage','FSCopyTree',{'From':'/sdcard/themes/'+name,'To':BASE+'/app/main.js','Overwrite':True});f('Storage','FSRemove',{'Path':'/sdcard/themes/'+name})
  def verify_release():
   # A long CDC JSON string can lose bytes while retaining valid JSON. Hash
   # inside the device instead of trusting a large FSReadText reply as bytes.
   check='/sdcard/resource-backups/maze-load-'+stamp+'-check'
   f('Storage','FSCopyTree',{'From':BASE+'/app/main.js','To':check+'/main.js','Overwrite':True})
   assert f('SdResources','InspectTree',{'Path':check})['sha256']==tree_hash({'main.js':release})
  assert not f('ChildMode','GetState')['enabled'],'Never bypass parent policy'
  for s in ['Audiobook','Radio','VoiceAssistant','LocalVoice','LearningAudio']:assert not f(s,'GetState')['active']
  modes=f('DeviceModes','GetState');volume=modes['resume_volume'];rotation=f('AutoRotation','GetState')
  app=next(a for a in f('SystemCore','ListApps') if a['manifest']['id']=='local.gravitymaze');id=app['app_id']
  f('SystemCore','StopApp',{'AppId':id})
  verify_release()
  progress=f('Storage','FSReadText',{'Path':BASE+'/data/progress.json'})
  backup='/sdcard/resource-backups/maze-load-'+stamp
  f('Storage','FSCopyTree',{'From':BASE+'/app/main.js','To':backup+'/main.js','Overwrite':False})
  f('Storage','FSCopyTree',{'From':BASE+'/data/progress.json','To':backup+'/progress.json','Overwrite':False})
  (runtime/'maze-load-recovery.json').write_text(json.dumps({'backup':backup,'volume':volume,'progress':progress,'version':version},indent=2),encoding='utf-8')
  try:
   upload(hook.encode(),'test');f('Storage','FSWriteText',{'Path':BASE+'/data/progress.json','Data':json.dumps({'schema':1,'level':10,'unlocked':10})})
   f('AudioPlayback','SetVolume',{'Volume':0});f('DeviceModes','Wake');f('SystemCore','StartApp',{'AppId':id})
   samples=[];refresh=[];start=time.monotonic()
   while time.monotonic()-start<35:
    time.sleep(1);samples.append(f('DeviceModes','GetResourceUsage'))
    if time.monotonic()-start>18:refresh.append(f('DeviceModes','ProfileRefresh',{'Force':False}))
   state=json.loads(f('Storage','FSReadText',{'Path':BASE+'/data/state.json'}));active=f('SystemCore','GetActiveApp')
   report.update(state=state,cpu_percent_max=max(s['cpu_percent'] for s in samples),internal_free_min=min(s['internal_free_bytes'] for s in samples),psram_free_min=min(s['psram_free_bytes'] for s in samples))
   if refresh:report['refresh_sample_mean_us']=sum(s['last_refresh_us'] for s in refresh)/len(refresh);report['refresh_sample_max_us']=max(s['last_refresh_us'] for s in refresh)
   assert active['app_id']==id and active['state']=='Running' and not active['last_error'],active
   assert state['level']==10 and state['camera_follow'] and state['wall_count']==125 and state['frames']>100 and state['mode']=='playing' and not state['error'],state
   assert state['x']>162 or state['y']>162,'Camera-follow region was not exercised'
   physics=state.get('profile',{}).get('Physics')
   if physics:
    report['physics_average_ms']=physics['ms']/physics['calls']
    if tuple(map(int,version.split('.'))) >= (0,1,4):assert report['physics_average_ms']<25,'Local collision calculation regressed'
   if tuple(map(int,version.split('.'))) == (0,1,5):
    changes=state['profile']['CameraMoves']['calls'];assert 1<changes<state['frames']/5,'Camera must turn pages without continuously scrolling';report['camera_moves']=changes
   elif tuple(map(int,version.split('.'))) >= (0,1,6):
    changes=state['profile']['CameraMoves']['calls'];assert changes>1,'Continuous camera follow was not exercised';report['camera_moves']=changes
   report.update(passed=True,state=state,cpu_percent_max=max(s['cpu_percent'] for s in samples),internal_free_min=min(s['internal_free_bytes'] for s in samples),psram_free_min=min(s['psram_free_bytes'] for s in samples))
  except BaseException as e:
   report['error']=str(e);raise
  finally:
   try:f('SystemCore','StopApp',{'AppId':id})
   except BaseException as e:report['stop_error']=str(e)
   upload(release,'release');f('Storage','FSWriteText',{'Path':BASE+'/data/progress.json','Data':progress})
   f('AudioPlayback','SetVolume',{'Volume':volume})
   verify_release()
   assert not f('AutoRotation','GetState')['motion_active'] and f('AutoRotation','GetState')['enabled']==rotation['enabled']
   report.update(release_restored=True,progress_restored=True,volume_restored=True)
   f('DeviceModes','Wake');f('SystemCore','StartApp',{'AppId':id})
   (runtime/'maze-load-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report))
if __name__=='__main__':main()
