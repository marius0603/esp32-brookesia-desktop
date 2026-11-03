"""Exercise the radio whitelist through a real encrypted BLE/Android-Java session.

Requires an idle, unlocked board. Never prints or saves the pairing secret.
Stops test audio, closes BLE and restores volume/deep-sleep choice in finally.
"""
import argparse,asyncio,base64,json,os,subprocess,sys,time
from pathlib import Path
from bleak import BleakClient,BleakScanner
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'codex-quota-monitor/tools'))
from deploy_audiobook_sleep import StoryClient

class TestClient(StoryClient):
 """Retain SPI failures as test failures while keeping cleanup RPCs usable."""
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs);self.hardware_errors=[]
  # A previous interrupted exclusive session may leave recent IDs cached.
  self.request_id=1000000000+(time.monotonic_ns()//1000)%2000000000
 def read_json(self):
  while True:
   try:return super().read_json()
   except RuntimeError as e:
    # Some HAL/board INFO records bypass USB's normal log suppression.
    # Keep them separate from RPC JSON; warnings and errors remain failures.
    if str(e).startswith(("invalid device response: b'I (",'invalid device response: b"I (')):
     self.diagnostic_lines.append(str(e).encode());continue
    if 'spi_common: spicommon_dma_setup_priv_buffer' not in str(e):raise
    self.hardware_errors.append(str(e))

def main():
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM5');p.add_argument('--tools',type=Path,required=True);p.add_argument('--classes',type=Path,required=True);a=p.parse_args()
 tools=json.loads(a.tools.read_text());report={'passed':False,'checks':[]};java=None
 output=ROOT/'codex-quota-monitor/runtime/radio-phone-verification.json'
 with TestClient(a.port,timeout=35) as usb:
  usb.hello()
  def f(s,n,args=None):return usb.call(s,n,args or {})['result']
  deadline=time.monotonic()+80
  while len(f('SystemCore','ListApps'))<13:
   assert time.monotonic()<deadline;time.sleep(1)
  original=f('DeviceModes','GetState');assert original['firmware_version']=='0.8.3-s3.45' and not original['screen_locked']
  assert not f('Audiobook','GetState')['active'] and not f('VoiceAssistant','GetState')['active'] and not f('Radio','GetState')['active'],'Finish current listening first'
  assert not f('ChildMode','GetState')['enabled'],'Use normal mode; do not change a parent PIN'
  assert not f('PhoneProvisioning','GetState')['active'],'Finish the existing Bluetooth session first'
  apps=f('SystemCore','ListApps');tracks=f('Audiobook','List')['tracks'];ids={x['manifest']['id']:x['app_id'] for x in apps}
  bookmark_path='/littlefs/audiobook-bookmark.json'
  bookmark=f('Storage','FSReadText',{'Path':bookmark_path}) if f('Storage','FSStat',{'Path':bookmark_path})['exists'] else None
  preservation=ROOT/('codex-quota-monitor/runtime/radio-phone-preserve-'+str(time.time_ns())+'.json')
  preservation.write_text(json.dumps({'modes':original,'bookmark':bookmark},ensure_ascii=False),encoding='utf-8')
  try:
   f('DeviceModes','Wake');f('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
   f('SystemCore','StartApp',{'AppId':ids['brookesia.general.settings']});f('PhoneProvisioning','StartRemote')
   deadline=time.monotonic()+20
   while True:
    setup=f('PhoneProvisioning','GetSetup')
    if setup['active']:break
    assert time.monotonic()<deadline;time.sleep(.3)
   env=os.environ.copy();env['XIAOMA_TEST_POP']=setup.pop('pop')
   java=subprocess.Popen([tools['java'],'-cp',str(a.classes)+os.pathsep+tools['bc'],'com.xiaoma.remote.ProtocolHarness'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=env)
   def protocol(cmd,data=None):
    java.stdin.write(cmd+(' '+base64.b64encode(data).decode() if data is not None else '')+'\n');java.stdin.flush();line=java.stdout.readline().strip();assert line
    return line if line=='OK' else base64.b64decode(line)
   async def run():
    device=await BleakScanner.find_device_by_filter(lambda d,ad:ad.local_name==setup['device_name'],timeout=25);assert device,'Bluetooth board not found'
    async with BleakClient(device,timeout=30) as client:
     session='1775ff51-6b43-439b-877c-060f2d9bed07';remote='1775ff55-6b43-439b-877c-060f2d9bed07'
     async def exchange(ep,data):
      await client.write_gatt_char(ep,data,response=True);await asyncio.sleep(.05);return bytes(await client.read_gatt_char(ep))
     response=await exchange(session,protocol('hello'));response=await exchange(session,protocol('prove',response));assert protocol('verify',response)=='OK'
     async def cmd(**request):
      reply=protocol('crypt',await exchange(remote,protocol('crypt',json.dumps(request).encode())))
      assert len(reply)<=480
      return json.loads(reply)
     def checked(name):report['checks'].append(name);print(name,flush=True)
     status=await cmd(cmd='status');assert status['ok'] and status['radio_supported']
     radio=await cmd(cmd='radio_status');assert radio['ok'] and not radio['active'];checked('authenticated idle status without autoplay')
     catalog=[]
     for page in range(4):
      response=await cmd(cmd='radio_stations',page=page);assert response['ok'] and response['total']==8
      catalog+=response['items'];assert response['more']==(page<3)
     expected=json.loads((ROOT/'brookesia-apps/radio/src/app/catalog.json').read_text(encoding='utf-8'))
     assert catalog==[{'id':s['id'],'name':s['display_name'],'group':s['group'],'sub':s['sub']} for s in expected]
     checked('all eight catalog stations match device UI')
     for request in [dict(cmd='radio_play',id='https://example.invalid/stream'),dict(cmd='radio_play',id='suzhou-qtfm-legacy'),dict(cmd='radio_stations',page=-1),dict(cmd='radio_timer',minutes=10),dict(cmd='radio_timer',minutes=15.5),dict(cmd='arbitrary_service',service='Storage')]:
      response=await cmd(**request);assert not response['ok'],request
     assert not (await cmd(cmd='radio_status'))['active'];checked('invalid station URL, legacy ID, page, timer and service rejected')
     for station in ['junior-0','cnr-news','suzhou-qtfm']:
      response=await cmd(cmd='radio_play',id=station);assert response['ok'],response
      deadline=time.monotonic()+40
      while True:
       state=f('Radio','GetState');assert not state['error'],state['error']
       if state['bytes_written']>0:break
       assert time.monotonic()<deadline,'No decoded audio';await asyncio.sleep(.5)
      active=f('SystemCore','GetActiveApp');assert active['app_id']==ids['local.radio']
      report.setdefault('audio_samples',[]).append({k:state[k] for k in ['station','bytes_written','decoder_stack_free','reader_stack_free','internal_free','internal_largest_block']})
      radio=await cmd(cmd='radio_status');assert radio['station']==station and radio['active']
      checked('BLE selected '+station+'; foreground and decoded PCM verified')
      if station=='junior-0':
       assert (await cmd(cmd='radio_pause'))['ok'];assert (await cmd(cmd='radio_status'))['paused']
       assert (await cmd(cmd='radio_resume'))['ok'];assert not (await cmd(cmd='radio_status'))['paused'];checked('pause and resume')
       for minutes in [15,30,45,0]:
        response=await cmd(cmd='radio_timer',minutes=minutes);assert response['ok'],response
        radio=await cmd(cmd='radio_status');assert radio['sleep_active']==bool(minutes)
        if minutes:assert minutes*60-5<=radio['sleep_remaining_seconds']<=minutes*60
       checked('15/30/45 minute timer and cancellation')
       for value in [25,65,35,75,40,original['resume_volume']]:
        started=time.monotonic()
        response=await cmd(cmd='volume',value=value);assert response['ok'],response
        elapsed=time.monotonic()-started;assert elapsed<3,elapsed
        await asyncio.sleep(.25)
        radio=await cmd(cmd='radio_status');assert radio['volume']==value,{'expected':value,'actual':radio['volume']}
        gain=f('DeviceModes','GetSpeakerVolume');assert gain['codec_volume']==value and gain['dac_register_valid'],gain
        report.setdefault('volume_samples',[]).append({'requested':value,'codec_volume':gain['codec_volume'],'dac_register':gain['dac_volume_register'],'response_seconds':round(elapsed,3)})
       assert report['volume_samples'][0]['dac_register']!=report['volume_samples'][1]['dac_register']
       checked('six volume changes with hardware gain and response latency while live streaming')
      assert (await cmd(cmd='radio_stop'))['ok'];assert not (await cmd(cmd='radio_status'))['active']
     checked('stop and replay another channel')
     assert (await cmd(cmd='stories',page=0))['ok'];assert (await cmd(cmd='apps',page=0))['ok'];checked('existing story/app list compatibility')
     assert (await cmd(cmd='play',id=0))['ok'];deadline=time.monotonic()+25
     while True:
      book=f('Audiobook','GetState')
      if book['active'] and book['bytes_written']>0:break
      assert time.monotonic()<deadline,'Story PCM unavailable';await asyncio.sleep(.4)
     for value in [35,75,original['resume_volume']]:
      assert (await cmd(cmd='volume',value=value))['ok'];await asyncio.sleep(.25)
      gain=f('DeviceModes','GetSpeakerVolume');assert gain['codec_volume']==value,gain
     assert (await cmd(cmd='stop'))['ok'];checked('existing audiobook playback and hardware gain regression')
     assert (await cmd(cmd='open',id=ids['brookesia.system.super.shell']))['ok']
   asyncio.run(run())
   assert f('Audiobook','List')['tracks']==tracks
   assert {x['manifest']['id']:x['manifest']['version'] for x in f('SystemCore','ListApps')}=={x['manifest']['id']:x['manifest']['version'] for x in apps}
   report.update(passed=True,stories_preserved=len(tracks),apps_preserved=len(apps))
  finally:
   if java:java.stdin.close();java.wait(timeout=10)
   cleanup=[]
   for service,name,params in [('Radio','Stop',{}),('Audiobook','Stop',{}),('SystemCore','StopApp',{'AppId':ids['local.radio']}),('SystemCore','StopApp',{'AppId':ids['local.audiobook']}),('PhoneProvisioning','Stop',{}),('AudioPlayback','SetVolume',{'Volume':original['resume_volume']}),('DeviceModes','SetAutoDeepSleep',{'Minutes':original['auto_deep_sleep_minutes']})]:
    try:f(service,name,params)
    except Exception as e:cleanup.append(service+'.'+name+': '+str(e))
   try:
    if bookmark is not None:
     f('Storage','FSWriteText',{'Path':bookmark_path,'Data':bookmark});assert f('Storage','FSReadText',{'Path':bookmark_path})==bookmark
    elif f('Storage','FSStat',{'Path':bookmark_path})['exists']:f('Storage','FSRemove',{'Path':bookmark_path})
   except Exception as e:cleanup.append('bookmark: '+str(e))
   report['cleanup_errors']=cleanup;report['spi_dma_errors']=len(usb.hardware_errors)
   if cleanup or usb.hardware_errors:report['passed']=False
   output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 assert report['passed'],report
 print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
