"""Real BLE commands through the Android APK's exact Java security code."""
import argparse,asyncio,base64,json,os,re,subprocess,sys,time,uuid,wave
from pathlib import Path
from bleak import BleakClient,BleakScanner
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'codex-quota-monitor/tools'))
from deploy_audiobook_sleep import StoryClient
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--tools',type=Path,required=True);p.add_argument('--classes',type=Path,required=True);p.add_argument('--lock-only',action='store_true');p.add_argument('--navigation-only',action='store_true');p.add_argument('--sweep',action='store_true');p.add_argument('--stories-only',action='store_true');p.add_argument('--require-wifi',action='store_true');a=p.parse_args();tools=json.loads(a.tools.read_text());before=json.loads((ROOT/'codex-quota-monitor/runtime/phone-remote-preservation.json').read_text(encoding='utf-8'))
 with StoryClient(a.port,timeout=30) as c:
  c.hello()
  def f(s,n,args=None):return c.call(s,n,args or {})['result']
  deadline=time.monotonic()+90
  while True:
   ready=f('SystemCore','ListApps')
   if len(ready)>=len(before['apps']) and any(x['manifest']['id']=='brookesia.system.super.shell' and x['state']=='Running' for x in ready):break
   assert time.monotonic()<deadline,'Desktop did not finish starting';time.sleep(1)
  wifi_deadline=time.monotonic()+60
  while True:
   wifi_connected=f('Wifi','GetGeneralState')=='Connected'
   if wifi_connected or not a.require_wifi:break
   assert time.monotonic()<wifi_deadline,'Saved Wi-Fi did not reconnect';time.sleep(1)
  # Match the user's Settings -> Bluetooth entry, closing any large UI first.
  settings=next(x for x in f('SystemCore','ListApps') if x['manifest']['id']=='brookesia.general.settings')
  f('SystemCore','StartApp',{'AppId':settings['app_id']})
  f('PhoneProvisioning','StartRemote');deadline=time.monotonic()+15
  while True:
   setup=f('PhoneProvisioning','GetSetup')
   if setup['active']:break
   assert setup['starting'] and time.monotonic()<deadline,setup['status'];time.sleep(.2)
  print('Desktop ready; encrypted BLE remote window active.',flush=True)
 assert re.fullmatch(r'[0-9]{4}',setup['pop']),'Remote pairing code must have four digits'
 env=os.environ.copy();env['XIAOMA_TEST_POP']=setup.pop('pop')
 java=subprocess.Popen([tools['java'],'-cp',str(a.classes)+os.pathsep+tools['bc'],'com.xiaoma.remote.ProtocolHarness'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,env=env,text=True)
 def protocol(command,data=None):
  java.stdin.write(command+(' '+base64.b64encode(data).decode() if data is not None else '')+'\n');java.stdin.flush();line=java.stdout.readline().strip();assert line;return line if line=='OK' else base64.b64decode(line)
 report={'wifi_connected_at_start':wifi_connected,'remote_pairing_digits':4}
 async def run():
  device=await BleakScanner.find_device_by_filter(lambda d,ad:ad.local_name==setup['device_name'],timeout=20);assert device
  async with BleakClient(device,timeout=25) as client:
   session='1775ff51-6b43-439b-877c-060f2d9bed07';remote='1775ff55-6b43-439b-877c-060f2d9bed07'
   assert client.services.get_characteristic(remote) and not client.services.get_characteristic('1775ff52-6b43-439b-877c-060f2d9bed07');report['mode_isolated']=True
   async def exchange(ep,data):
    await client.write_gatt_char(ep,data,response=True);await asyncio.sleep(.05);return bytes(await client.read_gatt_char(ep))
   response=await exchange(session,protocol('hello'));response=await exchange(session,protocol('prove',response));assert protocol('verify',response)=='OK';report['android_java_authenticated']=True
   async def cmd(**request):return json.loads(protocol('crypt',await exchange(remote,protocol('crypt',json.dumps(request).encode()))))
   original=await cmd(cmd='status');assert original['ok'] and not original['locked']
   if a.stories_only:
    with StoryClient(a.port,timeout=30) as usb:
     usb.hello()
     def f(service,name,args=None):return usb.call(service,name,args or {})['result']
     records=f('SystemCore','ListApps');ids={x['manifest']['id']:x['app_id'] for x in records};book=ids['local.audiobook'];shell=ids['brookesia.system.super.shell'];settings=ids['brookesia.general.settings']
     prefs={p:f('Storage','FSReadText',{'Path':p}) for p in ['/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json']}
     tracks=f('Audiobook','List')['tracks'];assert len(tracks)>=2
     def foreground():
      active=f('SystemCore','GetActiveApp');assert active and active['app_id']==book and active['state']=='Running' and not active['last_error'],active
     fixture_path=None
     try:
      assert (await cmd(cmd='volume',value=20))['ok']
      assert (await cmd(cmd='open',id=settings))['ok']
      assert not (await cmd(cmd='play',id=511))['ok'];assert f('SystemCore','GetActiveApp')['app_id']==settings
      for index in [1,0]:
       assert (await cmd(cmd='play',id=index))['ok'];await asyncio.sleep(1.4);foreground();state=f('Audiobook','GetState')
       assert state['active'] and state['path']==tracks[index]['path'] and state['bytes_written']>0,state
       assert (await cmd(cmd='pause'))['ok'];foreground();assert f('Audiobook','GetState')['state']=='Paused'
       assert (await cmd(cmd='resume'))['ok'];await asyncio.sleep(.3);foreground();assert f('Audiobook','GetState')['state']!='Paused'
      assert (await cmd(cmd='stop'))['ok'];foreground();assert not f('Audiobook','GetState')['active']
      expected=['小马和月亮灯','咕咚','小蝌蚪找妈妈','乌鸦喝水','小猴子下山','狐假虎威','坐井观天','小马过河','雪孩子','亡羊补牢']
      catalog=[]
      for page in range(4):
       response=await cmd(cmd='stories',page=page);assert response['ok'] and response['total']==10
       assert len(json.dumps(response,ensure_ascii=False).encode())<=480
       catalog.extend(item['name'] for item in response['items'])
      assert catalog==expected,catalog
      assert not (await cmd(cmd='mode',value='invalid'))['ok']
      def wait_audio(predicate,seconds=15):
       deadline=time.monotonic()+seconds
       while time.monotonic()<deadline:
        state=f('Audiobook','GetState');assert not state['error'],state
        if predicate(state):return state
        time.sleep(.15)
       raise AssertionError('Audio state did not reach expected transition: '+str(state))
      fixture_name='000-mode-check-'+uuid.uuid4().hex[:8]+'.wav';fixture_path='/sdcard/audiobooks/'+fixture_name
      fixture_file=ROOT/'codex-quota-monitor/runtime'/fixture_name
      with wave.open(str(fixture_file),'wb') as w:
       w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0'*(16000*2*4))
      assert usb.transfer('put',fixture_file,'sd-audiobooks/'+fixture_name,False)['ok']
      f('SystemCore','StopApp',{'AppId':book})
      for mode in ['sequence','random','repeat_one']:
       assert (await cmd(cmd='mode',value=mode))['ok'];await asyncio.sleep(1.2);foreground()
       assert (await cmd(cmd='play',id=0))['ok'];await asyncio.sleep(.7)
       status=await cmd(cmd='status');assert status['play_mode']==mode,status
       assert json.loads(f('Storage','FSReadText',{'Path':'/littlefs/audiobook-play-mode.json'}))['mode']==mode
       if mode=='repeat_one':
        wait_audio(lambda x:x['path']==fixture_path and x['state']=='Playing' and x['position']>=2)
        wait_audio(lambda x:x['path']==fixture_path and x['state']=='Playing' and x['position']<1)
       elif mode=='sequence':wait_audio(lambda x:x['path']==tracks[0]['path'] and x['state']=='Playing')
       else:wait_audio(lambda x:x['path']!=fixture_path and x['state']=='Playing')
       print('Live remote mode and EOF:',mode,'passed',flush=True)
      f('SystemCore','StopApp',{'AppId':book});f('Storage','FSRemove',{'Path':fixture_path});fixture_path=None
      checked=[]
      for index,track in enumerate(tracks):
       assert (await cmd(cmd='play',id=index))['ok'];await asyncio.sleep(.6);foreground()
       state=wait_audio(lambda x:x['active'] and x['path']==track['path'] and x['bytes_written']>0)
       assert state['title']==expected[index],state
       duration=int(state['duration']);assert duration>10
       checked.append(expected[index]);print('Story decoded on device:',expected[index],flush=True)
      assert (await cmd(cmd='stop'))['ok']
      report.update(story_selection_foreground=True,pause_resume_stop_foreground=True,decoded_audio_written=True,invalid_story_keeps_foreground=True,chinese_titles=catalog,live_remote_modes=['sequence','random','repeat_one'],all_story_decode=checked)
     finally:
      f('Audiobook','Stop');assert (await cmd(cmd='open',id=shell))['ok']
      if fixture_path and f('Storage','FSStat',{'Path':fixture_path})['exists']:f('Storage','FSRemove',{'Path':fixture_path})
      for path,old in prefs.items():f('Storage','FSWriteText',{'Path':path,'Data':old})
      await cmd(cmd='volume',value=original['volume'])
     for path,old in prefs.items():assert f('Storage','FSReadText',{'Path':path})==old
     report['bookmarks_mode_volume_restored']=True
    return
   if a.sweep:
    raw=bytearray()
    try:
     with StoryClient(a.port,timeout=25) as usb:
      usb.hello()
      def snapshot():return usb.call('SystemCore','ListApps',{})['result'],usb.call('PhoneProvisioning','GetState',{})['result']
      async def monitored_open(app_id):
       pending=asyncio.create_task(cmd(cmd='open',id=app_id));usb.serial.timeout=.02;next_probe=time.monotonic()+5
       try:
        while not pending.done():
         raw.extend(usb.serial.read(max(1,usb.serial.in_waiting)));await asyncio.sleep(.02)
         if time.monotonic()>=next_probe:
          usb.serial.timeout=25
          progress=usb.call('PhoneProvisioning','GetState',{})['result']
          print('Pending open',app_id,'phase',progress.get('app_lifecycle_stage','unknown'),'PSRAM',progress['psram_free_bytes'],'error',progress.get('last_task_error',''),flush=True)
          usb.serial.timeout=.02;next_probe=time.monotonic()+5
        response=await pending
        assert not any(x in raw for x in (b'Guru Meditation',b'assert failed:',b'Rebooting...',b'ESP-ROM:',b'Failed to allocate priv')),'Device fault; inspect private sweep UART log'
        return response
       finally:usb.serial.timeout=25
      records,baseline=snapshot();shell=next(x['app_id'] for x in records if x['manifest']['id']=='brookesia.system.super.shell');targets=[x for x in records if x['app_id']!=shell];rounds=[];minimum=10000000
      for cycle in range(3):
       for target in targets:
        response=await monitored_open(target['app_id']);assert response['ok'],(target['manifest']['id'],response);await asyncio.sleep(.6)
        records,metrics=snapshot();assert metrics['starts']==baseline['starts'] and metrics['active'],'BLE window changed during sweep'
        assert not metrics.get('last_task_error'),metrics.get('last_task_error')
        if a.require_wifi:assert usb.call('Wifi','GetGeneralState',{})['result']=='Connected','Wi-Fi disconnected during BLE sweep'
        running=[x for x in records if x['app_id']!=shell and x['state'] in ('Running','Paused')]
        assert len(running)==1 and running[0]['app_id']==target['app_id'],[(x['manifest']['id'],x['state']) for x in running]
        assert usb.call('SystemCore','GetActiveApp',{})['result']['app_id']==target['app_id'],'Wrong foreground app'
        assert not running[0]['last_error'],running[0]['last_error'];minimum=min(minimum,metrics['psram_free_bytes']);print('Sweep',cycle+1,target['manifest']['id'],'OK','PSRAM',metrics['psram_free_bytes'],'internal',metrics['internal_free_bytes'],'DMA',metrics['largest_dma_block'],flush=True)
       assert (await monitored_open(shell))['ok'];await asyncio.sleep(.5);records,metrics=snapshot();assert not any(x['app_id']!=shell and x['state'] in ('Running','Paused') for x in records);rounds.append(metrics['psram_free_bytes']);print('After home',cycle+1,metrics['psram_free_bytes'],flush=True)
    finally:(ROOT/'codex-quota-monitor/runtime/phone-remote-sweep-uart.log').write_bytes(raw)
    assert rounds[-1]>=rounds[-2]-262144,rounds
    report.update(sweep_rounds=3,apps_per_round=len(targets),single_foreground_enforced=True,after_home_psram=rounds,minimum_psram=minimum);return
   if a.navigation_only:
    def app_states():
     with StoryClient(a.port,timeout=25) as usb:
      usb.hello();return [],usb.call('SystemCore','GetActiveApp',{})['result']
    with StoryClient(a.port,timeout=25) as usb:
     usb.hello();all_apps=usb.call('SystemCore','ListApps',{})['result']
    ids={x['manifest']['id']:x['app_id'] for x in all_apps};settings=ids['brookesia.general.settings'];shell=ids['brookesia.system.super.shell'];clock=ids['local.flipclock']
    for cycle in range(2):
     assert (await cmd(cmd='open',id=clock))['ok'];await asyncio.sleep(.4);assert app_states()[1]['app_id']==clock
     for repeat in range(2):
      assert (await cmd(cmd='open',id=settings))['ok'];await asyncio.sleep(.4);current=app_states()[1];assert current['app_id']==settings and current['state']=='Running'
     assert (await cmd(cmd='open',id=shell))['ok'];await asyncio.sleep(.4);records,current=app_states();assert not current or current['app_id']==shell
    pet=ids['local.virtualpet']
    for repeat in range(2):
     response=await cmd(cmd='open',id=pet);assert response['ok'],response;await asyncio.sleep(.4);records,current=app_states();assert current['app_id']==pet and current['state']=='Running'
     assert (await cmd(cmd='open',id=shell))['ok'];await asyncio.sleep(.2)
    assert (await cmd(cmd='open',id=settings))['ok'];report['pet_foreground_and_reopen']=True;report['native_settings_foreground_and_repeat_open']=True;report['shell_home_and_repeat_cycles']=True;return
   if a.lock_only:
    assert (await cmd(cmd='lock'))['ok'];assert (await cmd(cmd='status'))['locked']
    assert not (await cmd(cmd='wake'))['ok'];assert not (await cmd(cmd='volume',value=40))['ok'];report['locked_controls_rejected']=True;return
   try:
    assert not (await cmd(cmd='volume',value=101))['ok'];assert not (await cmd(cmd='brightness',value=-1))['ok'];assert not (await cmd(cmd='arbitrary_service',service='Storage'))['ok'];report['invalid_commands_rejected']=True
    assert (await cmd(cmd='volume',value=40))['ok'];assert (await cmd(cmd='status'))['volume']==40
    assert (await cmd(cmd='brightness',value=60))['ok'];assert (await cmd(cmd='status'))['brightness']==60;report['volume_brightness']=True
    apps=await cmd(cmd='apps',page=0);stories=await cmd(cmd='stories',page=0);assert apps['ok'] and apps['items'] and stories['ok'] and stories['items'];report['lists']=True
    with StoryClient(a.port,timeout=25) as c:
     c.hello();all_apps=c.call('SystemCore','ListApps',{})['result'];settings=next(x for x in all_apps if x['manifest']['id']=='brookesia.general.settings')['app_id']
    assert (await cmd(cmd='open',id=settings))['ok'];report['open_app']=True
   finally:
    await cmd(cmd='volume',value=original['volume']);await cmd(cmd='brightness',value=original['brightness'])
 try:asyncio.run(run())
 finally:
  java.stdin.close();java.wait(timeout=10)
  with StoryClient(a.port,timeout=25) as c:c.hello();c.call('PhoneProvisioning','Stop',{})
 report['passed']=True;(ROOT/('codex-quota-monitor/runtime/phone-remote-story-verification.json' if a.stories_only else 'codex-quota-monitor/runtime/phone-remote-navigation-verification.json' if a.navigation_only else 'codex-quota-monitor/runtime/phone-remote-sweep-verification.json' if a.sweep else 'codex-quota-monitor/runtime/phone-remote-device-verification.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
