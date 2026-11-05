"""Exercise assistant audio and foreground startup with real encrypted BLE.

Records three seconds locally; no microphone upload. Requires idle audio,
normal/unlocked desktop, original SD, XiaoZhi binding/Wi-Fi, Java tools and Bleak.
Restores the Windows Bluetooth radio state and closes test sessions.
"""
import asyncio,sys,json,time,os,subprocess,base64,argparse
from pathlib import Path
from bleak import BleakClient,BleakScanner
from winrt.windows.devices.radios import Radio,RadioKind,RadioState
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'codex-quota-monitor/tools'))
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',default='COM5');p.add_argument('--tools',type=Path,required=True);p.add_argument('--classes',type=Path,required=True);args=p.parse_args()
from maintenance_client import SharedPowerDiagnosticClient
async def main():
 radios=[r for r in await Radio.get_radios_async() if r.kind==RadioKind.BLUETOOTH];old=[r.state for r in radios]
 for r in radios:await r.set_state_async(RadioState.ON)
 java=None;owned=False;report={'passed':False,'tests':[]}
 try:
  with SharedPowerDiagnosticClient(args.port,timeout=15) as c:
   c.hello()
   def f(s,n,p=None):return c.call_timeout(s,n,p or {})['result']
   assert not f('ChildMode','GetState')['enabled']
   assert not f('DeviceModes','GetState')['screen_locked']
   for service in ['Audiobook','Radio','LocalVoice','VoiceAssistant']:assert not f(service,'GetState')['active'],service
   assert json.loads(f('Storage','FSReadText',{'Path':'/littlefs/voice-assistant-backend.json'}))['backend']=='xiaozhi','Select XiaoZhi mode first'
   assert not f('PhoneProvisioning','GetState')['active'],'Close the existing BLE session before diagnostics'
   f('PhoneProvisioning','Stop')
   for _ in range(100):
    if not f('PhoneProvisioning','GetState')['active']:break
    await asyncio.sleep(.2)
   f('PhoneProvisioning','StartRemote');owned=True
   for _ in range(40):
    setup=f('PhoneProvisioning','GetSetup')
    if setup['active'] and 'pop' in setup:break
    await asyncio.sleep(.3)
   env=os.environ.copy();env['XIAOMA_TEST_POP']=setup.pop('pop');tools=json.loads(args.tools.read_text())
   java=subprocess.Popen([tools['java'],'-cp',str(args.classes)+os.pathsep+tools['bc'],'com.xiaoma.remote.ProtocolHarness'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=env)
   def protocol(cmd,data=None):
    java.stdin.write(cmd+(' '+base64.b64encode(data).decode() if data is not None else '')+'\n');java.stdin.flush();line=java.stdout.readline().strip();assert line
    return line if line=='OK' else base64.b64decode(line)
   device=await BleakScanner.find_device_by_filter(lambda d,a:a.local_name==setup['device_name'],timeout=25);assert device
   async with BleakClient(device,timeout=30) as client:
    session='1775ff51-6b43-439b-877c-060f2d9bed07'
    async def exchange(ep,data):
     await client.write_gatt_char(ep,data,response=True);await asyncio.sleep(.05);return bytes(await client.read_gatt_char(ep))
    response=await exchange(session,protocol('hello'));response=await exchange(session,protocol('prove',response));assert protocol('verify',response)=='OK'
    print('Encrypted BLE connected',flush=True)
    for service in ['LocalVoice','VoiceAssistant']*2:
     f(service,'TestMicrophone');end=time.monotonic()+20;last={}
     while time.monotonic()<end:
      last=f(service,'GetState')
      if last.get('error'):raise RuntimeError(service+': '+last['error'])
      if last['captured_frames']>=48000 and last['played_bytes']>=90000:break
      await asyncio.sleep(.3)
     assert last['captured_frames']>=48000 and last['played_bytes']>=90000,last
     report['tests'].append({'service':service,'frames':last['captured_frames'],'played':last['played_bytes']});print(report['tests'][-1],flush=True)
     f(service,'Disconnect')
     for _ in range(40):
      if not f(service,'GetState')['active']:break
      await asyncio.sleep(.1)
    apps=f('SystemCore','ListApps');aid=next(a['app_id'] for a in apps if a['manifest']['id']=='local.voiceassistant')
    for attempt in range(3):
     f('SystemCore','StartApp',{'AppId':aid});deadline=time.monotonic()+25
     while True:
      v=f('VoiceAssistant','GetState')
      if v['error']:raise RuntimeError('UI start: '+v['error'])
      if v['channel']:break
      assert time.monotonic()<deadline,v['state'];await asyncio.sleep(.4)
     print('UI small-horse assistant ready with encrypted BLE: '+str(attempt+1),flush=True)
     f('SystemCore','RequestCloseApp',{'AppId':aid})
     deadline=time.monotonic()+20
     while f('VoiceAssistant','GetState')['active']:
      assert time.monotonic()<deadline;await asyncio.sleep(.2)
    report['ui_ready_rounds']=3
   f('PhoneProvisioning','Stop')
   for _ in range(100):
    if not f('PhoneProvisioning','GetState')['active']:break
    await asyncio.sleep(.2)
   for attempt in range(3):
    f('PhoneProvisioning','StartRemote')
    for _ in range(100):
     state=f('PhoneProvisioning','GetState')
     if state['active']:break
     if not state['starting']:raise RuntimeError(state['status'])
     await asyncio.sleep(.2)
    assert state['active'],state['status']
    print('Warm BLE restart '+str(attempt+1)+' block='+str(state['start_largest_dma_block']),flush=True)
    f('PhoneProvisioning','Stop')
    for _ in range(100):
     if not f('PhoneProvisioning','GetState')['active']:break
     await asyncio.sleep(.2)
   report['passed']=True
 finally:
  if java:java.stdin.close();java.wait(timeout=10)
  try:
   if owned:
    with SharedPowerDiagnosticClient(args.port,timeout=10) as cleanup:
     cleanup.hello()
     for service,method in [('LocalVoice','Disconnect'),('VoiceAssistant','Disconnect'),('PhoneProvisioning','Stop')]:cleanup.call_timeout(service,method,{})
  except Exception as e:
   report['cleanup_error']=str(e);report['passed']=False
  for r,s in zip(radios,old):await r.set_state_async(s)
  (ROOT/'codex-quota-monitor/runtime/assistant-real-ble-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
asyncio.run(main())
