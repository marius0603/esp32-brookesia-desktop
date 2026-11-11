"""Repeated real BLE/nav/audio cycles; verify the controller can warm-start again.
No online APIs, microphone recording, pairing secrets or route text in reports.
"""
import argparse,asyncio,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'codex-quota-monitor/tools'))
from maintenance_client import SharedPowerDiagnosticClient
from winrt.windows.devices.radios import Radio,RadioKind,RadioState

def board(action,port):
 with SharedPowerDiagnosticClient(port,timeout=35) as c:
  c.hello()
  def f(s,n,a=None):return c.call_timeout(s,n,a or {})['result']
  return action(f)
def idle(f):
 end=time.monotonic()+30
 while True:
  b=f('PhoneProvisioning','GetState')
  if not b['active'] and not b['starting']:return b
  assert time.monotonic()<end;time.sleep(.2)
def main():
 p=argparse.ArgumentParser();p.add_argument('--rounds',type=int,default=3);p.add_argument('--port',default='COM5');p.add_argument('--tools',type=Path,required=True);p.add_argument('--classes',type=Path,required=True);a=p.parse_args();assert 1<=a.rounds<=6
 report={'passed':False,'rounds':[]};out=ROOT/'codex-quota-monitor/runtime/navigation-memory-warm.json'
 def save():out.write_text(json.dumps(report,indent=2)+'\n')
 def prepare(f):
  m=f('DeviceModes','GetState');assert m['firmware_version']=='0.8.3-s3.66' and not m['screen_locked']
  assert not f('ChildMode','GetState')['enabled']
  for s in ['Audiobook','Radio','VoiceAssistant','LocalVoice','LearningAudio']:assert not f(s,'GetState')['active']
  b=f('PhoneProvisioning','GetState');assert not b['active'] and not b['starting']
  f('DeviceModes','SetAutoDeepSleep',{'Minutes':0});f('AudioPlayback','SetVolume',{'Volume':0});return m
 original=board(prepare,a.port)
 async def run():
  saved=[(r,r.state) for r in await Radio.get_radios_async() if r.kind==RadioKind.BLUETOOTH];assert saved
  try:
   for r,s in saved:
    if s!=RadioState.ON:await r.set_state_async(RadioState.ON)
   for round in range(a.rounds):
    def home(f):
     f('PhoneProvisioning','Stop');idle(f)
     apps=f('SystemCore','ListApps');shell=next(x for x in apps if x['manifest']['id']=='brookesia.system.super.shell')
     active=f('SystemCore','GetActiveApp')
     if active and active['app_id']!=shell['app_id']:f('SystemCore','StopApp',{'AppId':active['app_id']})
     if f('SystemCore','GetActiveApp').get('app_id')!=shell['app_id']:f('SystemCore','StartApp',{'AppId':shell['app_id']})
    board(home,a.port)
    result=await asyncio.to_thread(subprocess.run,[sys.executable,'-X','utf8',str(ROOT/'phone-remote/tests/verify_navigation_device.py'),'--port',a.port,'--tools',str(a.tools),'--classes',str(a.classes)])
    assert result.returncode==0,'Navigation/BLE cycle failed'
    def snapshot(f):
     b=idle(f);time.sleep(.3);b=f('PhoneProvisioning','GetState')
     assert b['largest_dma_block']>=b['required_dma_block'] and b['dma_free_bytes']>=40960,b
     assert b['memory_rejections']==0,b
     return {k:b[k] for k in ['start_attempts','memory_rejections','largest_dma_block','dma_free_bytes','start_largest_dma_block','start_dma_free_bytes','internal_free_bytes','psram_free_bytes']}
    report['rounds'].append(board(snapshot,a.port));save();print('Warm navigation/BLE round '+str(round+1)+' passed',flush=True)
  finally:
   for r,s in saved:
    if r.state!=s:await r.set_state_async(s)
 try:
  asyncio.run(run());report['passed']=True
 finally:
  def restore(f):
   f('PhoneProvisioning','Stop');idle(f);f('LearningAudio','StopNavigationPrompt');f('AudioPlayback','SetVolume',{'Volume':original['resume_volume']});f('DeviceModes','SetAutoDeepSleep',{'Minutes':original['auto_deep_sleep_minutes']})
   report['volume_restored']=f('DeviceModes','GetState')['resume_volume']==original['resume_volume']
  board(restore,a.port);save()
 print(json.dumps(report))
if __name__=='__main__':main()
