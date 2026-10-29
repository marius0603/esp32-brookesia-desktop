"""Verify repeated BLE windows, idle restart and preservation without exposing codes."""
import argparse,json,time
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--cycles',type=int,default=5);p.add_argument('--baseline',type=Path,help='Optional private snapshot from before deployment');a=p.parse_args();assert 1<=a.cycles<=10
 report={'passed':False,'windows':[]};before=json.loads(a.baseline.read_text(encoding='utf-8')) if a.baseline else None
 with StoryClient(a.port,timeout=30) as c:
  c.hello()
  def f(s,n,args=None):return c.call(s,n,args or {})['result']
  deadline=time.monotonic()+90
  while True:
   apps=f('SystemCore','ListApps')
   if (before is None or len(apps)>=len(before['apps'])) and any(x['app_id']==1 and x['state']=='Running' for x in apps) and f('Wifi','GetGeneralState')=='Connected':break
   assert time.monotonic()<deadline,'Device not ready';time.sleep(1)
  modes=f('DeviceModes','GetState');assert modes['firmware_version']=='0.8.3-s3.32'
  if before is None:
   preferences={}
   for path in ('/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json'):
    if f('Storage','FSStat',{'Path':path})['exists']:preferences[path]=f('Storage','FSReadText',{'Path':path})
   before={'apps':apps,'modes':modes,'tracks':f('Audiobook','List')['tracks'],'volume':f('AudioPlayback','GetVolume'),'preferences':preferences}
  report['baseline']=f('PhoneProvisioning','GetState');assert not report['baseline']['active']
  previous=None
  for i in range(a.cycles):
   f('PhoneProvisioning','Start');deadline=time.monotonic()+15
   while True:
    state=f('PhoneProvisioning','GetSetup')
    if state['active']:break
    if not state['starting']:raise RuntimeError('Provisioning not started: '+json.dumps(state,ensure_ascii=True))
    assert time.monotonic()<deadline,'BLE start timed out';time.sleep(.2)
   code=state.pop('pop');assert len(code)==8 and code!=previous;previous=code
   f('PhoneProvisioning','Stop');deadline=time.monotonic()+15
   while True:
    closed=f('PhoneProvisioning','GetSetup')
    if not closed['active'] and not closed['starting']:break
    assert time.monotonic()<deadline,'BLE stop timed out';time.sleep(.2)
   assert 'pop' not in closed
   report['windows'].append({k:closed[k] for k in ('internal_free_bytes','largest_dma_block','stack_free_min_bytes')})
   print('Provisioning window',i+1,'closed; temporary code removed.',flush=True);time.sleep(.5)
  assert f('Audiobook','List')['tracks']==before['tracks'] and f('AudioPlayback','GetVolume')==before['volume']
  assert f('DeviceModes','GetState')['desktop_theme_index']==before['modes']['desktop_theme_index']
  for path,old in before['preferences'].items():
   if old is not None:assert f('Storage','FSReadText',{'Path':path})==old
  settings=next(x for x in apps if x['manifest']['id']=='brookesia.general.settings');f('DeviceModes','Wake');f('SystemCore','StartApp',{'AppId':settings['app_id']})
  active=f('SystemCore','GetActiveApp');assert active['app_id']==settings['app_id'] and active['state']=='Running' and not active['last_error'],active
  report.update(passed=True,wifi_connected=True,pairing_code_rotates=True,pairing_code_removed_on_close=True,stories=len(before['tracks']),volume=before['volume'],theme=modes['desktop_theme_index'],settings_opened=True)
 (ROOT/'codex-quota-monitor/runtime/phone-provisioning-device-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k!='baseline'}))
if __name__=='__main__':main()
