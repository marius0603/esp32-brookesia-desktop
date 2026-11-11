"""Exercise compact navigation via real encrypted BLE and Android's exact Java protocol.

Only synthetic directions. No AMap/Internet/location calls and no audio changes.
Requires an idle, unlocked device outside child mode. Never print pairing secrets.
"""
import argparse,asyncio,base64,json,os,subprocess,sys,time
from pathlib import Path
from bleak import BleakClient,BleakScanner
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'codex-quota-monitor/tools'))
from maintenance_client import SharedPowerDiagnosticClient

def main():
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM5');p.add_argument('--tools',type=Path,required=True);p.add_argument('--classes',type=Path,required=True);a=p.parse_args()
 tools=json.loads(a.tools.read_text());a.classes.mkdir(parents=True,exist_ok=True)
 subprocess.run([tools['javac'],'-encoding','UTF-8','-cp',tools['bc'],'-d',str(a.classes),str(ROOT/'phone-remote/android/src/com/xiaoma/remote/Protocol.java'),str(ROOT/'phone-remote/tests/ProtocolHarness.java')],check=True)
 report={'passed':False,'online_requests':0};java=None
 with SharedPowerDiagnosticClient(a.port,timeout=35) as usb:
  usb.hello()
  def f(s,n,args=None):return usb.call_timeout(s,n,args or {})['result']
  original=f('DeviceModes','GetState');assert not original['screen_locked']
  assert not f('ChildMode','GetState')['enabled'],'Exit child mode on device; do not change PIN'
  for s in ['Audiobook','Radio','VoiceAssistant','LocalVoice']:assert not f(s,'GetState')['active'],'Finish listening first'
  assert not f('PhoneProvisioning','GetState')['active'],'Finish existing Bluetooth session first'
  deadline=time.monotonic()+90
  while True:
   apps=f('SystemCore','ListApps')
   if len(apps)>=15 and any(x['manifest']['id']=='brookesia.system.super.shell' and x['state']=='Running' for x in apps):break
   assert time.monotonic()<deadline,'Wait for complete desktop startup';time.sleep(1)
  ids={x['manifest']['id']:x['app_id'] for x in apps};assert 'local.navigation' in ids
  assert not f('DeviceModes','GetNavigationState')['received']
  try:
   f('DeviceModes','Wake');f('SystemCore','StartApp',{'AppId':ids['brookesia.general.settings']});f('PhoneProvisioning','StartRemote')
   deadline=time.monotonic()+25
   while True:
    setup=f('PhoneProvisioning','GetSetup')
    if setup['active']:break
    assert time.monotonic()<deadline,setup.get('status');time.sleep(.2)
   env=os.environ.copy();env['XIAOMA_TEST_POP']=setup.pop('pop')
   java=subprocess.Popen([tools['java'],'-cp',str(a.classes)+os.pathsep+tools['bc'],'com.xiaoma.remote.ProtocolHarness'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=env)
   def protocol(command,data=None):
    java.stdin.write(command+(' '+base64.b64encode(data).decode() if data is not None else '')+'\n');java.stdin.flush();line=java.stdout.readline().strip();assert line
    return line if line=='OK' else base64.b64decode(line)
   async def run():
    device=await BleakScanner.find_device_by_filter(lambda d,ad:ad.local_name==setup['device_name'],timeout=25);assert device,'BLE device not found'
    async with BleakClient(device,timeout=30) as ble:
     async def exchange(ep,data):
      await ble.write_gatt_char(ep,data,response=True);await asyncio.sleep(.08);return bytes(await ble.read_gatt_char(ep))
     ep='1775ff51-6b43-439b-877c-060f2d9bed07'
     response=await exchange(ep,protocol('hello'));response=await exchange(ep,protocol('prove',response));assert protocol('verify',response)=='OK'
     async def send(packet):
      raw=json.dumps(packet,ensure_ascii=False,separators=(',',':')).encode();assert len(raw)<=256
      result=await exchange('1775ff55-6b43-439b-877c-060f2d9bed07',protocol('crypt',raw));return json.loads(protocol('crypt',result))
     assert (await send({'cmd':'status'}))['navigation_supported']
     frame={'cmd':'nav','s':'1234567890abcdef','q':1,'m':0,'t':0,'d':200,'r':1500,'e':900,'n':'示例道路','z':0}
     for change in [{'q':2},{'t':99},{'d':-2},{'q':1.5},{'n':'路'*25},{'n':'路\n名'},{'s':'not-a-session'}]:
      assert not (await send(dict(frame,**change)))['ok']
     assert f('SystemCore','GetActiveApp')['app_id']==ids['brookesia.general.settings']
     assert (await send(frame))['ok']
     await asyncio.sleep(1.5)
     active=f('SystemCore','GetActiveApp');assert active['app_id']==ids['local.navigation'] and active['state']=='Running' and not active['last_error'],active
     current=f('DeviceModes','GetNavigationState');assert current['active'] and current['road']=='示例道路' and current['distance']==200
     deadline=time.monotonic()+7
     while True:
      sound=f('LearningAudio','GetState');assert not sound['error'],sound
      if sound['played_bytes']>0:break
      assert time.monotonic()<deadline,'Local prompt did not write PCM';await asyncio.sleep(.2)
     deadline=time.monotonic()+6
     while f('LearningAudio','GetState')['active']:
      assert time.monotonic()<deadline;await asyncio.sleep(.2)
     f('LearningAudio','PlayNavigationPrompt',{'Turn':1,'Stage':2})
     await asyncio.sleep(.6);sound=f('LearningAudio','GetState');assert sound['played_bytes']>0 and not sound['error'],sound
     report['local_voice_pcm_written']=True
     assert not (await send(frame))['ok'];assert not (await send(dict(frame,q=2,m=1)))['ok']
     for q,t in enumerate([1,2,3,4,5,6,7],2):
      frame.update(q=q,t=t,d=150);assert (await send(frame))['ok'];await asyncio.sleep(1.1)
      current=f('DeviceModes','GetNavigationState');assert current['turn']==t and current['sequence']==q
      assert not f('SystemCore','GetActiveApp')['last_error']
     print('BLE: authenticated compact frames, validation, all arrows and foreground passed.',flush=True)
     await asyncio.sleep(16)
     current=f('DeviceModes','GetNavigationState');assert current['stale'] and not current['active'];report['stale_after_15s']=True
     frame.update(q=9,t=1);assert (await send(frame))['ok'];assert f('DeviceModes','GetNavigationState')['active']
     frame.update(q=10,z=2);assert (await send(frame))['ok'];assert f('DeviceModes','GetNavigationState')['phase']==2
     assert not (await send(dict(frame,q=11,z=0)))['ok']
     frame.update(s='abcdef1234567890',q=1,z=0,m=1);assert (await send(frame))['ok']
     assert f('DeviceModes','GetNavigationState')['source']==1
     frame.update(q=2,z=2);assert (await send(frame))['ok']
     frame.update(s='bbccddeeff001122',q=1,z=0,m=2,d=-1,r=-1,e=-1,t=7,n='高德导航中');assert (await send(frame))['ok']
     unknown=f('DeviceModes','GetNavigationState');assert unknown['source']==2 and unknown['distance']==-1 and unknown['remaining']==-1
     frame.update(q=2,z=2);assert (await send(frame))['ok'];report['notification_unknown_fields']=True
     report.update(authenticated_android_protocol=True,invalid_rejected=True,sequence_guard=True,source_guard=True,all_arrows=True,stop_terminal=True,new_session=True)
   asyncio.run(run())
  finally:
   if java:
    java.stdin.close();java.wait(timeout=10)
   f('LearningAudio','StopNavigationPrompt');f('PhoneProvisioning','Stop')
   # Return to navigation for the physical display check; does not start audio.
   f('SystemCore','StartApp',{'AppId':ids['local.navigation']})
   assert f('DeviceModes','GetState')['resume_volume']==original['resume_volume']
   after=f('SystemCore','ListApps');assert {x['manifest']['id']:x['manifest']['version'] for x in after}=={x['manifest']['id']:x['manifest']['version'] for x in apps}
  report.update(passed=True,apps_preserved=len(apps),volume_preserved=True)
 (ROOT/'codex-quota-monitor/runtime/navigation-ble-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
