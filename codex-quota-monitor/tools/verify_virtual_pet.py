"""Exercise all native pet frames, restore the release BPK and check background resume."""
import argparse,json,re,time,zipfile
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
from deploy_learning import install_app
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/'codex-quota-monitor/runtime'
VERSION=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps']['local.virtualpet']
RELEASE=ROOT/('packages/apps/local.virtualpet.debug.'+VERSION+'.bpk')
def capture(c,raw):
 original=c.serial.readline
 def readline(*args,**kwargs):
  while True:
   data=original(*args,**kwargs);raw.extend(data)
   if re.fullmatch(rb'I PET_(FRAME_OK:pet_[a-z]+_\d|STEP_OK:\d+:[a-z]+:(true|false))\r?\n',data):continue
   return data
 c.serial.readline=readline
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);a=p.parse_args()
 test=RUNTIME/'virtual-pet-test.bpk';log=RUNTIME/'virtual-pet-usb.log';raw=bytearray()
 with zipfile.ZipFile(RELEASE) as src,zipfile.ZipFile(test,'w',zipfile.ZIP_DEFLATED) as dst:
  for name in src.namelist():
   data=src.read(name)
   if name=='app/main.js':
    s=data.decode('utf-8')
    needle="cache.src=src;frames++;";assert s.count(needle)==1
    s=s.replace(needle,needle+"console.log('I PET_FRAME_OK:'+src);")
    needle="on_timer(){if(!hidden){foreground();tick();}return true;}";assert s.count(needle)==1
    replacement="""on_timer(){if(!hidden){foreground();tick();globalThis.petTest=(globalThis.petTest||0)+1;const t=globalThis.petTest;
if(t===2||t===4||t===6)showPose('pet_idle_'+(t/2-1),Date.now());
if(t===40)interact('feed');if(t===72)interact('pet');if(t===104)interact('schedule');if(t===112)interact('sleepPreview');if(t===184)interact('schedule');if(t===192)interact('back');
if([40,72,104,112,184,192,240].includes(t))console.log('I PET_STEP_OK:'+t+':'+mode+':'+panel);
}return true;}"""
    data=s.replace(needle,replacement).encode('utf-8')
   dst.writestr(name,data)
 report={'passed':False}
 try:
  install_app(a.port,test)
  with StoryClient(a.port,timeout=35) as c:
   capture(c,raw);c.hello()
   def f(s,n,args=None):return c.call(s,n,args or {})['result']
   deadline=time.monotonic()+80
   while True:
    apps=f('SystemCore','ListApps')
    if any(x['app_id']==1 and x['state']=='Running' for x in apps):break
    assert time.monotonic()<deadline,'Desktop not ready';time.sleep(1)
   pet=next(x for x in apps if x['manifest']['id']=='local.virtualpet')
   f('DeviceModes','Wake');f('SystemCore','StartApp',{'AppId':pet['app_id']})
   profile_before=f('DeviceModes','ProfileRefresh',{'Force':False});started=time.monotonic()
   c.goodbye();c.serial.timeout=.2
   end=time.monotonic()+55
   while time.monotonic()<end:
    raw.extend(c.serial.read(max(1,c.serial.in_waiting)))
    if b'PET_STEP_OK:240:' in raw:break
   expected=['pet_idle_0','pet_idle_1','pet_idle_2','pet_eat_0','pet_eat_1','pet_eat_2','pet_sleep_0','pet_sleep_1']
   assert all(('PET_FRAME_OK:'+frame).encode() in raw for frame in expected),'Some native frames did not display'
   assert all(('PET_STEP_OK:'+str(n)+':').encode() in raw for n in (40,72,104,112,184,192,240)),'Some interactions failed'
   assert not any(x in raw for x in (b'Guru Meditation',b'assert failed:',b'Rebooting...',b'ESP-ROM:')),'Device restarted'
   c.serial.timeout=35;c.hello()
   profile_after=f('DeviceModes','ProfileRefresh',{'Force':False});elapsed=time.monotonic()-started
   active=f('SystemCore','GetActiveApp');assert active['app_id']==pet['app_id'] and active['state']=='Running' and not active['last_error'],active
   state=json.loads(f('Storage','FSReadText',{'Path':'/sdcard/pets/xiaoli/state.json'}))
   assert state['clock_synced'] and state['frames']>=8
   report.update(frames_checked=expected,interactions_checked=['feed','pet','schedule','sleepPreview','back'],memory=f('LocalVoice','GetState').get('free_psram_bytes'),render_profile={'before':profile_before,'after':profile_after,'test_seconds':round(elapsed,2),'refreshes':profile_after['refresh_count']-profile_before['refresh_count']})
 finally:
  log.write_bytes(raw)
  with StoryClient(a.port,timeout=35) as c:
   capture(c,raw);c.hello()
   pet=next((x for x in c.call('SystemCore','ListApps',{})['result'] if x['manifest']['id']=='local.virtualpet'),None)
   if pet and pet['state'] in ('Running','Paused','Starting'):c.call('SystemCore','StopApp',{'AppId':pet['app_id']})
  install_app(a.port,RELEASE)
 with StoryClient(a.port,timeout=35) as c:
  capture(c,raw);c.hello()
  def f(s,n,args=None):return c.call(s,n,args or {})['result']
  apps=f('SystemCore','ListApps');pet=next(x for x in apps if x['manifest']['id']=='local.virtualpet');clock=next(x for x in apps if x['manifest']['id']=='local.flipclock')
  app_path='/sdcard/apps/local.virtualpet'
  assert f('Storage','FSStat',{'Path':app_path+'/manifest.json'})['exists'],'Pet should be installed on SD'
  f('SystemCore','StartApp',{'AppId':pet['app_id']});time.sleep(6)
  f('DeviceModes','Wake')
  before=json.loads(f('Storage','FSReadText',{'Path':'/sdcard/pets/xiaoli/state.json'}))
  f('SystemCore','StartApp',{'AppId':clock['app_id']});time.sleep(2)
  paused=json.loads(f('Storage','FSReadText',{'Path':'/sdcard/pets/xiaoli/state.json'}));assert paused['paused'],paused
  paused_memory=f('LocalVoice','GetState')['free_psram_bytes']
  f('SystemCore','StartApp',{'AppId':pet['app_id']});time.sleep(6)
  resumed=json.loads(f('Storage','FSReadText',{'Path':'/sdcard/pets/xiaoli/state.json'}));assert not resumed['paused'] and not resumed['config_fallback'],resumed
  active=f('SystemCore','GetActiveApp');assert active['app_id']==pet['app_id'] and active['state']=='Running' and not active['last_error'],active
  with zipfile.ZipFile(RELEASE) as z:
   for name in ('app/main.js','res/images/index.json','manifest.json'):
    assert f('Storage','FSReadText',{'Path':app_path+'/'+name}).replace('\r\n','\n')==z.read(name).decode().replace('\r\n','\n')
  latest=json.loads((RUNTIME/'virtual-pet-latest.json').read_text(encoding='utf-8'));preserved=json.loads((Path(latest['folder'])/'preservation.json').read_text(encoding='utf-8'))
  assert f('AudioPlayback','GetVolume')==preserved['volume'] and f('Audiobook','List')['tracks']==preserved['tracks']
  assert f('DeviceModes','GetState')['desktop_theme_index']==preserved['theme']
  for path,old in preserved['preferences'].items():
   if old is not None:assert f('Storage','FSReadText',{'Path':path})==old
  report.update(passed=True,release_restored=True,pause_resume=True,paused_psram_free=paused_memory,stories=len(preserved['tracks']),volume=preserved['volume'],theme=preserved['theme'])
 log.write_bytes(raw)
 (RUNTIME/'virtual-pet-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report,ensure_ascii=True))
if __name__=='__main__':main()
