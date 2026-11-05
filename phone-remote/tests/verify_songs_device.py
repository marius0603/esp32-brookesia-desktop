"""Check nursery songs over real encrypted BLE using the APK's Java protocol.

Requires s3.48+, idle audio, unlocked normal mode, and the original SD card.
Restores volume, native modes, bookmarks, deep sleep and the closed BLE window.
Pairing secrets are passed only in the Java child's environment, never logged.
"""
import argparse,asyncio,base64,json,os,subprocess,sys,time
from pathlib import Path
from bleak import BleakClient,BleakScanner
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'codex-quota-monitor/tools'))
from maintenance_client import SharedPowerDiagnosticClient

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',default='COM5');p.add_argument('--tools',type=Path,required=True);p.add_argument('--classes',type=Path,required=True);p.add_argument('--catalog-rounds',type=int,default=1);a=p.parse_args();assert 1<=a.catalog_rounds<=10
 tools=json.loads(a.tools.read_text());output=ROOT/'codex-quota-monitor/runtime/songs-phone-verification.json'
 report={'passed':False,'checks':[],'reply_max_bytes':0};java=None
 def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 with SharedPowerDiagnosticClient(a.port,timeout=35) as usb:
  usb.hello()
  def f(s,n,p=None):return usb.call_timeout(s,n,p or {})['result']
  deadline=time.monotonic()+60
  while True:
   apps=f('SystemCore','ListApps')
   if len(apps)>=14:break
   assert time.monotonic()<deadline;time.sleep(1)
  original=f('DeviceModes','GetState');assert original['firmware_version'] in ('0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51') and not original['screen_locked']
  original_book=f('Audiobook','GetState')
  assert not original_book['active'] and not original_book['sleep_active']
  assert not f('Radio','GetState')['active'] and not f('VoiceAssistant','GetState')['active']
  assert not f('ChildMode','GetState')['enabled'],'Never bypass parent settings to run diagnostics'
  assert not f('PhoneProvisioning','GetState')['active'],'Finish the existing Bluetooth session first'
  ids={x['manifest']['id']:x['app_id'] for x in apps};songs=f('Audiobook','ListSongs')['tracks'];stories=f('Audiobook','List')['tracks']
  assert len(songs)==20 and len(stories)==30
  f('SystemCore','StopApp',{'AppId':ids['local.nurserysongs']})
  saved={}
  for path in ['/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json','/sdcard/apps/local.nurserysongs/data/player.json','/sdcard/apps/local.nurserysongs/data/play-mode.json']:
   saved[path]=f('Storage','FSReadText',{'Path':path}) if f('Storage','FSStat',{'Path':path})['exists'] else None
  private=ROOT/('codex-quota-monitor/runtime/songs-phone-preserve-'+str(time.time_ns())+'.json')
  private.write_text(json.dumps({'files':saved,'volume':original['resume_volume'],'book':original_book},ensure_ascii=False),encoding='utf-8')
  try:
   f('DeviceModes','Wake');f('DeviceModes','SetAutoDeepSleep',{'Minutes':0});f('AudioPlayback','SetVolume',{'Volume':0})
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
   def checked(name):report['checks'].append(name);save();print(name,flush=True)
   async def run():
    device=await BleakScanner.find_device_by_filter(lambda d,ad:ad.local_name==setup['device_name'],timeout=25);assert device,'Bluetooth board not found'
    async with BleakClient(device,timeout=30) as client:
     session='1775ff51-6b43-439b-877c-060f2d9bed07';remote='1775ff55-6b43-439b-877c-060f2d9bed07'
     async def exchange(ep,data):
      await client.write_gatt_char(ep,data,response=True);await asyncio.sleep(.05);return bytes(await client.read_gatt_char(ep))
     response=await exchange(session,protocol('hello'));response=await exchange(session,protocol('prove',response));assert protocol('verify',response)=='OK'
     async def cmd(**request):
      reply=protocol('crypt',await exchange(remote,protocol('crypt',json.dumps(request).encode())))
      report['reply_max_bytes']=max(report['reply_max_bytes'],len(reply));assert len(reply)<=480
      response=json.loads(reply);report['last_request']=request;report['last_response']=response
      return response
     async def expect_play(id):
      deadline=time.monotonic()+25
      while True:
       s=f('Audiobook','GetState');assert not s['error'],s
       if s['state']=='Playing' and s['path']==songs[id]['path'] and s['bytes_written']>=32000:return s
       assert time.monotonic()<deadline,'No song PCM';await asyncio.sleep(.25)
     status=await cmd(cmd='status');assert status['ok'] and status['songs_supported'] and status['radio_supported']
     s=await cmd(cmd='song_status');assert s['ok'] and not s['active'];checked('authenticated idle status without autoplay')
     for catalog_round in range(a.catalog_rounds):
      catalog=[]
      for page in range(7):
       r=await cmd(cmd='songs',page=page);assert r['ok'] and r['total']==20 and r['more']==(page<6),r;catalog+=r['items']
      assert catalog==[{'id':i,'name':t['title']} for i,t in enumerate(songs)]
     report['catalog_rounds']=a.catalog_rounds
     empty=await cmd(cmd='songs',page=7);assert empty['items']==[] and not empty['more'];checked('all 20 songs across seven pages, separate from 30 stories')
     for request in [dict(cmd='songs',page=-1),dict(cmd='songs',page=.5),dict(cmd='song_play',id=20),dict(cmd='song_play',id=-1),dict(cmd='song_play',id='https://example.invalid/song.mp3'),dict(cmd='song_mode',value='bad'),dict(cmd='song_timer',minutes=10),dict(cmd='song_timer',minutes=15.5),dict(cmd='arbitrary_service',service='Storage')]:
      assert not (await cmd(**request))['ok'],request
     checked('invalid IDs, URL, page, mode, timer and arbitrary service rejected')
     assert (await cmd(cmd='song_mode',value='sequence'))['ok']
     assert (await cmd(cmd='song_play',id=0))['ok'];await expect_play(0)
     assert f('SystemCore','GetActiveApp')['app_id']==ids['local.nurserysongs']
     s=await cmd(cmd='song_status');assert s['active'] and s['id']==0 and s['title']==songs[0]['title']
     status=await cmd(cmd='status');assert not status['story_active'] and not status['story_title'];checked('song selection opens device song app and produces PCM; story status stays separate')
     assert (await cmd(cmd='song_pause'))['ok'];assert (await cmd(cmd='song_status'))['state']=='Paused'
     assert (await cmd(cmd='song_resume'))['ok'];await expect_play(0)
     assert (await cmd(cmd='song_next'))['ok'];await expect_play(1)
     assert (await cmd(cmd='song_previous'))['ok'];await expect_play(0)
     assert (await cmd(cmd='song_previous'))['ok'];await expect_play(19)
     assert (await cmd(cmd='song_next'))['ok'];await expect_play(0);checked('pause/resume, previous/next and library wrap')
     for mode in ['random','repeat_one','sequence']:
      path=f('Audiobook','GetState')['path'];assert (await cmd(cmd='song_mode',value=mode))['ok']
      await asyncio.sleep(1.3);s=await cmd(cmd='song_status');assert s['play_mode']==mode and f('Audiobook','GetState')['path']==path
      stored=json.loads(f('Storage','FSReadText',{'Path':'/sdcard/apps/local.nurserysongs/data/play-mode.json'}))
      assert stored['mode']==mode
      assert f('Audiobook','GetState')['play_mode']==original_book['play_mode']
     checked('three shared song modes preserve story mode and current track')
     for minutes in [15,30,45,0]:
      assert (await cmd(cmd='song_timer',minutes=minutes))['ok'];s=await cmd(cmd='song_status');assert s['sleep_active']==bool(minutes)
      if minutes:assert minutes*60-5<=s['sleep_remaining_seconds']<=minutes*60
     checked('15/30/45 minute fade timer and cancellation')
     for value in [20,45,0]:
      began=time.monotonic();assert (await cmd(cmd='volume',value=value))['ok'];elapsed=time.monotonic()-began;assert elapsed<3
      await asyncio.sleep(.3);gain=f('DeviceModes','GetSpeakerVolume');assert gain['codec_volume']==value and gain['dac_register_valid']
      assert (await cmd(cmd='song_status'))['volume']==value
      report.setdefault('volume_samples',[]).append({'volume':value,'codec_volume':gain['codec_volume'],'dac_register':gain['dac_volume_register'],'response_seconds':round(elapsed,3)})
     checked('phone volume changes actual speaker gain and song status')
     first=f('Audiobook','GetState')['bytes_written'];began=time.monotonic()
     while time.monotonic()-began<20:await asyncio.sleep(3);assert (await cmd(cmd='song_status'))['active']
     s=f('Audiobook','GetState');assert s['pcm_starvations']==0 and s['write_gap_max_us']<100000 and s['bytes_written']-first>20*64000*.9,s
     report['continuity']={k:s[k] for k in ['pcm_starvations','write_gap_max_us','pcm_stack_free_min_bytes']};checked('20 second BLE polling with continuous song PCM')
     assert (await cmd(cmd='song_stop'))['ok'];assert not (await cmd(cmd='song_status'))['active']
     assert (await cmd(cmd='stories',page=0))['total']==30 and (await cmd(cmd='apps',page=0))['total']==14
     assert (await cmd(cmd='radio_status'))['ok'] and (await cmd(cmd='radio_stations',page=0))['total']==8
     assert (await cmd(cmd='play',id=0))['ok']
     for request in [dict(cmd='song_stop'),dict(cmd='song_pause'),dict(cmd='song_resume'),dict(cmd='song_timer',minutes=15)]:assert not (await cmd(**request))['ok']
     s=f('Audiobook','GetState');assert s['active'] and s['path']==stories[0]['path']
     assert (await cmd(cmd='stop'))['ok'];checked('song-only commands do not interrupt stories; existing stories, apps and radio compatible')
     assert (await cmd(cmd='open',id=ids['brookesia.system.super.shell']))['ok']
   asyncio.run(run());assert f('Audiobook','List')['tracks']==stories and f('Audiobook','ListSongs')['tracks']==songs
   report.update(passed=True,stories_preserved=30,songs_preserved=20,apps_preserved=14)
  finally:
   if java:java.stdin.close();java.wait(timeout=10)
   cleanup=[]
   for service,name,args in [('Audiobook','Stop',{}),('SystemCore','StopApp',{'AppId':ids['local.nurserysongs']}),('SystemCore','StopApp',{'AppId':ids['local.audiobook']}),('PhoneProvisioning','Stop',{}),('Audiobook','SetSongMode',{'Mode':original_book['song_play_mode']}),('AudioPlayback','SetVolume',{'Volume':original['resume_volume']}),('DeviceModes','SetAutoDeepSleep',{'Minutes':original['auto_deep_sleep_minutes']})]:
    try:f(service,name,args)
    except Exception as e:cleanup.append(service+'.'+name+': '+str(e))
   for path,data in saved.items():
    try:
     if data is not None:f('Storage','FSWriteText',{'Path':path,'Data':data})
     elif f('Storage','FSStat',{'Path':path})['exists']:f('Storage','FSRemove',{'Path':path})
    except Exception as e:cleanup.append('restore preference: '+str(e))
   report['known_power_dependency_logs']=usb.power_dependency_logs;report['cleanup_errors']=cleanup;report['passed']=report['passed'] and not cleanup;save()
   if cleanup:raise RuntimeError('Cleanup failed; inspect private report')
 print('Encrypted BLE nursery-song checks passed; original preferences and volume restored.',flush=True)

if __name__=='__main__':main()
