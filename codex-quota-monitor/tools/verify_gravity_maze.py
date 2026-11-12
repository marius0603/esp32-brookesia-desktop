"""Real device motion-lease, silent cue and app-start checks; no synthetic input API."""
import json,time
from pathlib import Path
from maintenance_client import SharedPowerDiagnosticClient
ROOT=Path(__file__).resolve().parents[2]
def main():
 report={'passed':False}
 with SharedPowerDiagnosticClient('COM5',timeout=35) as c:
  c.hello()
  def f(s,n,a=None):return c.call_timeout(s,n,a or {})['result']
  mode=f('DeviceModes','GetState');assert mode['firmware_version']=='0.8.3-s3.67' and not mode['screen_locked']
  assert not f('ChildMode','GetState')['enabled'],'Test requires ordinary mode; do not bypass parent PIN'
  for s in ['Audiobook','Radio','VoiceAssistant','LocalVoice','LearningAudio']:assert not f(s,'GetState')['active']
  apps=f('SystemCore','ListApps');ids={a['manifest']['id']:a['app_id'] for a in apps};assert len(apps)==16 and 'local.gravitymaze' in ids
  original=f('AutoRotation','GetState');lease=f('AutoRotation','AcquireMotion')['token'];motion=f('AutoRotation','ReadMotion',{'Token':lease});time.sleep(.45);sample=f('AutoRotation','ReadMotion',{'Token':lease});assert sample['samples']-motion['samples']>=8 and sample['sample_age_ms']<250
  assert sample['degrees']==motion['degrees'] and sample['enabled']==original['enabled']
  f('AutoRotation','ReleaseMotion',{'Token':lease});assert not f('AutoRotation','GetState')['motion_active']
  lease=f('AutoRotation','AcquireMotion')['token'];time.sleep(2.8);assert not f('AutoRotation','GetState')['motion_active'];assert f('AutoRotation','GetState')['enabled']==original['enabled'];report['lease_and_expiry']=True
  f('DeviceModes','Wake');f('SystemCore','StartApp',{'AppId':ids['local.gravitymaze']});time.sleep(1)
  app=f('SystemCore','GetActiveApp');assert app['app_id']==ids['local.gravitymaze'] and app['state']=='Running' and not app['last_error'],app
  volume=mode['resume_volume']
  try:
   f('AudioPlayback','SetVolume',{'Volume':0})
   if not mode['do_not_disturb']:
    for cue in [0,1]:
     f('LearningAudio','PlayGameCue',{'Cue':cue});time.sleep(.12);sound=f('LearningAudio','GetState');assert sound['played_bytes']>0 and sound['output_channels']==2 and sound['external_stack'] and not sound['error'],sound
     end=time.monotonic()+5
     while f('LearningAudio','GetState')['active']:assert time.monotonic()<end;time.sleep(.1)
    report['cue_pcm_and_external_stack']=True
  finally:f('LearningAudio','StopGameCue');f('AudioPlayback','SetVolume',{'Volume':volume})
  f('SystemCore','StopApp',{'AppId':ids['local.gravitymaze']});time.sleep(.3)
  assert not f('AutoRotation','GetState')['motion_active']
  ble=f('PhoneProvisioning','GetState')
  if not ble['active'] and not ble['starting']:
   f('PhoneProvisioning','StartRemote');end=time.monotonic()+15
   while True:
    ble=f('PhoneProvisioning','GetState')
    if ble['active']:break
    assert time.monotonic()<end,ble['status'];time.sleep(.2)
   report['ble_warm_start']=True;f('PhoneProvisioning','Stop');time.sleep(.5)
  report['memory_before_game']={k:f('PhoneProvisioning','GetState')[k] for k in ['largest_dma_block','dma_free_bytes','psram_free_bytes','memory_rejections']}
  f('DeviceModes','Wake');f('SystemCore','StartApp',{'AppId':ids['local.gravitymaze']});time.sleep(1)
  app=f('SystemCore','GetActiveApp');assert app['app_id']==ids['local.gravitymaze'] and app['state']=='Running' and not app['last_error'],app
  end=time.monotonic()+30
  while True:
   state=json.loads(f('Storage','FSReadText',{'Path':'/sdcard/apps/local.gravitymaze/data/state.json'}))
   if state['mode']=='ready':break
   assert state['mode']=='loading' and time.monotonic()<end,state;time.sleep(.25)
  assert not state['error'];report['state']=state
  assert f('DeviceModes','GetState')['resume_volume']==volume
  assert len(f('Audiobook','List')['tracks'])==30 and len(f('Audiobook','ListSongs')['tracks'])==30
  report.update(passed=True,apps=16,stories=30,songs=30,volume_preserved=True,resource_usage=f('DeviceModes','GetResourceUsage'))
 (ROOT/'codex-quota-monitor/runtime/maze-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
