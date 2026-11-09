"""Check real cold-boot storage state and foundation services; never reads PINs.

Remove/insert the card only with the device powered off. This tool does not
unmount a live card, change parent policy or test PIN values.
"""
import argparse
import json
from pathlib import Path
import time
from maintenance_client import MaintenanceClient

ROOT=Path(__file__).resolve().parents[1]
FOUNDATION={'brookesia.system.super.shell','brookesia.general.settings',
            'brookesia.general.files','brookesia.general.app_store','local.childmode'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM5')
 p.add_argument('--with-sd',action='store_true',help='Verify restoration after reinserting and rebooting')
 p.add_argument('--speaker-test',action='store_true',help='Play a short local synthetic tone and verify hardware gain; no microphone/network')
 a=p.parse_args();report={'passed':False,'with_sd':a.with_sd}
 output=ROOT/('runtime/foundation-with-sd.json' if a.with_sd else 'runtime/foundation-without-sd.json')
 with MaintenanceClient(a.port,timeout=20) as c:
  c.hello()
  def f(s,n,v=None):return c.call_timeout(s,n,v or {})['result']
  layout=f('SystemCore','GetStorageLayout')
  card=any(v['available'] and v['root_path']=='/sdcard' for v in layout['external'])
  assert card==a.with_sd,'Card state differs; perform a cold boot after physically changing the card'
  apps={x['id']:x for x in f('SystemCore','AppStorageInfo')['apps']}
  assert FOUNDATION<=set(apps)
  if not a.with_sd:assert set(apps)==FOUNDATION,apps
  else:
   current=f('DeviceModes','GetState')['firmware_version']
   assert len(apps)==(14 if current in ('0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57','0.8.3-s3.58') else 13)
   if current in ('0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57','0.8.3-s3.58'):assert len(f('Audiobook','ListSongs')['tracks'])==20
   for app in apps.values():
    if app['runtime'] and app['requires_sd']:assert app['path'].startswith('/sdcard/apps/')
   assert len(f('Audiobook','List')['tracks'])==30
  assert apps['local.childmode']['path']=='/littlefs/apps/local.childmode'
  child=f('ChildMode','GetState')
  report['parent_pin_configured']=child['configured']
  modes=f('DeviceModes','GetState');report['firmware']=modes['firmware_version']
  assert modes['timeout_seconds']==600
  f('DeviceModes','Wake')
  if not child['enabled']:
   settings=apps['brookesia.general.settings']['app_id']
   f('SystemCore','StartApp',{'AppId':settings})
   assert f('SystemCore','GetActiveApp')['app_id']==settings
   f('SystemCore','StopApp',{'AppId':settings})
   report['settings_opened']=True
  # No audio is played. Verify desired volume and read the real codec state.
  initial=modes['resume_volume'];target=max(0,initial-5) if initial else 5
  try:
   f('AudioPlayback','SetVolume',{'Volume':target});time.sleep(.3)
   assert f('DeviceModes','GetState')['resume_volume']==target
   report['codec']=f('DeviceModes','GetSpeakerVolume')
   # Without PCM, the codec can retain its idle gain; the requested volume
   # is verified above. Actual gain is checked separately during test audio.
  finally:f('AudioPlayback','SetVolume',{'Volume':initial})
  assert f('DeviceModes','GetState')['resume_volume']==initial
  report['volume_restored']=initial
  if a.speaker_test:
   assert not child['enabled'] and not modes['do_not_disturb'],'Use normal mode outside quiet hours for the audible diagnostic'
   assert not f('VoiceAssistant','GetState')['active'],'Finish current voice session first'
   report['audible_gain_samples']=[]
   try:
    f('AudioPlayback','SetVolume',{'Volume':10})
    f('VoiceAssistant','TestSpeaker');time.sleep(1)
    for target in (10,40,0):
     f('AudioPlayback','SetVolume',{'Volume':target});time.sleep(.6)
     value=f('DeviceModes','GetSpeakerVolume')
     assert value['codec_volume']==target,value
     report['audible_gain_samples'].append({'requested':target,**value})
   finally:
    f('VoiceAssistant','Disconnect');deadline=time.monotonic()+15
    while f('VoiceAssistant','GetState')['active']:
     assert time.monotonic()<deadline,'Synthetic writer did not stop'
     time.sleep(.2)
    f('AudioPlayback','SetVolume',{'Volume':initial})
  if not a.with_sd:
   fixture=ROOT/'runtime/sd-storage-check/fixture-1.0.0.bpk'
   assert fixture.is_file(),'Run the disposable installer fixture before the no-card check'
   try:c.transfer('install_bpk',fixture,None,False)
   except RuntimeError as e:
    assert str(e).startswith('sd_required:'),str(e)
    report['install_rejected_without_card']=True
   else:raise AssertionError('A BPK must not install without the card')
  report.update(passed=True,apps=list(apps),layout=layout)
 output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Foundation and USB maintenance verified; card present:',card,flush=True)

if __name__=='__main__':main()
