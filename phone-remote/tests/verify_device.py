"""Real BLE commands through the Android APK's exact Java security code."""
import argparse,asyncio,base64,json,os,subprocess,sys,time
from pathlib import Path
from bleak import BleakClient,BleakScanner
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'codex-quota-monitor/tools'))
from deploy_audiobook_sleep import StoryClient
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--tools',type=Path,required=True);p.add_argument('--classes',type=Path,required=True);p.add_argument('--lock-only',action='store_true');a=p.parse_args();tools=json.loads(a.tools.read_text());before=json.loads((ROOT/'codex-quota-monitor/runtime/phone-remote-preservation.json').read_text(encoding='utf-8'))
 with StoryClient(a.port,timeout=30) as c:
  c.hello()
  def f(s,n,args=None):return c.call(s,n,args or {})['result']
  deadline=time.monotonic()+90
  while len(f('SystemCore','ListApps'))<len(before['apps']):
   assert time.monotonic()<deadline;time.sleep(1)
  f('PhoneProvisioning','StartRemote');deadline=time.monotonic()+15
  while True:
   setup=f('PhoneProvisioning','GetSetup')
   if setup['active']:break
   assert setup['starting'] and time.monotonic()<deadline,setup['status'];time.sleep(.2)
 env=os.environ.copy();env['XIAOMA_TEST_POP']=setup.pop('pop')
 java=subprocess.Popen([tools['java'],'-cp',str(a.classes)+os.pathsep+tools['bc'],'com.xiaoma.remote.ProtocolHarness'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,env=env,text=True)
 def protocol(command,data=None):
  java.stdin.write(command+(' '+base64.b64encode(data).decode() if data is not None else '')+'\n');java.stdin.flush();line=java.stdout.readline().strip();assert line;return line if line=='OK' else base64.b64decode(line)
 report={}
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
 report['passed']=True;(ROOT/'codex-quota-monitor/runtime/phone-remote-device-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
