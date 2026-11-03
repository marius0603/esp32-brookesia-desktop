"""Exercise real network reception, decoding and shared codec controls on device."""
import argparse,json,time
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM5');p.add_argument('--sample-seconds',type=int,default=10);p.add_argument('--station',help='Verify one catalog ID, e.g. suzhou-qtfm, for a longer run');p.add_argument('--exclude-station',action='append',default=[],help='Skip a known problematic catalog ID');p.add_argument('--listen-volume',type=int,default=0,help='0-100, default mute; restored at exit');p.add_argument('--leave-playing',action='store_true');a=p.parse_args()
 if not 1<=a.sample_seconds<=3600:p.error('--sample-seconds must be between 1 and 3600')
 if not 0<=a.listen_volume<=100:p.error('--listen-volume must be between 0 and 100')
 stations=json.loads((ROOT/'brookesia-apps/radio/stations.json').read_text(encoding='utf-8'))['stations']
 if a.station:
  stations=[s for s in stations if s['id']==a.station]
  if not stations:p.error('Unknown catalog station ID')
 if set(a.exclude_station)-{s['id'] for s in stations}:p.error('Unknown excluded catalog station ID')
 stations=[s for s in stations if s['id'] not in a.exclude_station]
 if not stations:p.error('No stations selected')
 output=ROOT/'codex-quota-monitor/runtime/radio-verification.json';report={'passed':False,'phase':'playback','scope':'single_station' if a.station else 'selected_stations' if a.exclude_station else 'all_stations','excluded_stations':a.exclude_station,'sample_seconds':a.sample_seconds,'stations':[]}
 def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 with StoryClient(a.port,timeout=30) as c:
  c.hello()
  def f(s,n,p=None):return c.call(s,n,p or {})['result']
  def radio():return f('Radio','GetState')
  def wait(predicate,seconds=35):
   end=time.monotonic()+seconds
   while time.monotonic()<end:
    s=radio()
    if s['error']:raise RuntimeError(s['error'])
    if predicate(s):return s
    time.sleep(.25)
   raise TimeoutError('Radio state deadline: '+json.dumps(s,ensure_ascii=False))
  before=f('DeviceModes','GetState');tracks=f('Audiobook','List')['tracks'];apps=f('SystemCore','ListApps')
  ready=time.monotonic()+45
  while True:
   app=next((x for x in apps if x['manifest']['id']=='local.radio'),None)
   if app:break
   assert time.monotonic()<ready,'Radio app discovery timed out'
   time.sleep(1);apps=f('SystemCore','ListApps')
  assert app['manifest']['version']=='0.1.0'
  assert not f('Audiobook','GetState')['active'],'Finish audiobook before running this diagnostic'
  assert not f('ChildMode','GetState')['enabled'],'Use normal mode for live radio validation'
  f('DeviceModes','Wake');f('DeviceModes','SetAutoDeepSleep',{'Minutes':0});f('AudioPlayback','SetVolume',{'Volume':a.listen_volume})
  try:
   f('Radio','Stop')
   if app['state'] in ('Running','Paused'):f('SystemCore','StopApp',{'AppId':app['app_id']})
   f('SystemCore','StartApp',{'AppId':app['app_id']});assert not radio()['active'],'App must not autoplay'
   report['silent_start']=True
   for station in stations:
    row={'id':station['id'],'name':station['name'],'passed':False};report['stations'].append(row)
    print('Testing '+station['name'],flush=True)
    try:
     f('Radio','Play',{'Station':station['id']});s=wait(lambda s:s['state']=='Playing' and s['bytes_written']>=32000)
     start=s['bytes_written'];began=time.monotonic();row['samples']=[]
     while time.monotonic()-began<a.sample_seconds:
      time.sleep(max(0,min(15,a.sample_seconds-(time.monotonic()-began))));s=radio()
      row['samples'].append({'elapsed_seconds':time.monotonic()-began,'bytes_written':s['bytes_written'],'bytes_received':s['bytes_received'],'pcm_starvations':s['pcm_starvations'],'write_gap_max_us':s['write_gap_max_us'],'state':s['state']});save()
      print(station['name']+' '+json.dumps(row['samples'][-1],ensure_ascii=False),flush=True)
     elapsed=time.monotonic()-began
     row.update(playable=True,native_error=s['error'],played_seconds=(s['bytes_written']-start)/64000,elapsed_seconds=elapsed,**{key:s[key] for key in ('bytes_written','bytes_received','pcm_starvations','write_gap_max_us','reconnects','sample_rate','channels','decoder_stack_free','reader_stack_free','internal_free','psram_free','decode_errors','decoded_frames','decode_max_us','input_stalls','wifi_rssi','network_read_max_us','network_read_calls','decode_total_us','internal_largest_block','wifi_ps_mode','server_address')})
     assert not s['error'] and s['bytes_written']>start,s['error'] or 'No PCM output'
     assert s['pcm_starvations']==0 and row['played_seconds']>=elapsed*.90 and s['write_gap_max_us']<100000 and s['decode_errors']==0,'Playback continuity below target'
     row['passed']=True
     print('Playback data advancing: '+station['name'],flush=True)
    except (RuntimeError,TimeoutError,AssertionError) as e:
     row['error']=str(e);print('Not verified: '+station['name']+' '+str(e)[:140],flush=True)
    finally:f('Radio','Stop');save()
   report['phase']='controls';save()
   working=next((s for s in report['stations'] if s['passed']),None);assert working,'No station played'
   f('Radio','Play',{'Station':working['id']});wait(lambda s:s['bytes_written']>32000)
   f('Radio','Pause');time.sleep(.3);paused=radio()['bytes_written'];time.sleep(.5);assert radio()['bytes_written']==paused
   f('Radio','Resume');wait(lambda s:s['bytes_written']>paused);report['pause_resume']=True
   volume_checks=[]
   for value in [10,45,0]:
    f('AudioPlayback','SetVolume',{'Volume':value});time.sleep(.3);v=f('DeviceModes','GetSpeakerVolume');assert v['codec_volume']==value,v
    volume_checks.append({'requested':value,'codec':v['codec_volume'],'dac':v.get('dac_volume_register')})
   report['volume_controls']=volume_checks
   f('DeviceModes','SetDoNotDisturb',{'Enabled':True});time.sleep(.4);assert f('DeviceModes','GetSpeakerVolume')['codec_volume']==0
   f('DeviceModes','SetDoNotDisturb',{'Enabled':before['manual_do_not_disturb']});report['do_not_disturb']=True
   for minutes in [15,30,45,0]:
    f('Radio','SetSleepTimer',{'Minutes':minutes});s=radio();assert s['sleep_active']==(minutes>0)
    assert max(0,minutes*60-5)<=s['sleep_remaining_seconds']<=minutes*60
   report['timer_presets']=[0,15,30,45]
   f('Radio','TestSleepTimer');s=wait(lambda s:not s['active'] and s['state']=='TimerEnded',20);report['sleep_timer']=True
   memory=[]
   for i in range(3):
    f('Radio','Play',{'Station':working['id']});wait(lambda s:s['bytes_written']>16000);f('Radio','Stop');time.sleep(.3);memory.append(radio())
   report['reopen_memory']=[{k:s[k] for k in ('internal_free','psram_free')} for s in memory]
   assert memory[-1]['psram_free']>=memory[0]['psram_free']-65536,'Unexpected PSRAM loss across reopen'
   f('Radio','Play',{'Station':working['id']});wait(lambda s:s['bytes_written']>32000)
   f('Wifi','TriggerGeneralAction',{'Action':'Disconnect'});time.sleep(6)
   f('Wifi','TriggerGeneralAction',{'Action':'Connect'});time.sleep(2)
   prior=radio()['bytes_written'];s=wait(lambda s:s['bytes_written']>prior+32000,40);report['wifi_recovered']=s['reconnects']>0
   assert report['wifi_recovered'],'No reconnect observed'
   rejected=False
   try:f('Audiobook','Play',{'Path':tracks[0]['path'],'Position':0})
   except RuntimeError:rejected=True
   assert rejected,'Audiobook must not take radio codec ownership'
   f('Radio','Stop');f('Audiobook','Play',{'Path':tracks[0]['path'],'Position':0})
   rejected=False
   try:f('Radio','Play',{'Station':working['id']})
   except RuntimeError:rejected=True
   assert rejected,'Radio must not take audiobook codec ownership'
   f('Audiobook','Stop');report['audio_ownership']=True
   assert f('Audiobook','List')['tracks']==tracks
   report['preserved_stories']=len(tracks);report['passed']=all(s['passed'] for s in report['stations']);report['phase']='complete';save()
  except Exception as e:
   report['execution_error']=type(e).__name__+': '+str(e);report['passed']=False;save();raise
  finally:
   report['cleanup_errors']=[]
   for service,name,args in [('Radio','Stop',{}),('DeviceModes','SetDoNotDisturb',{'Enabled':before['manual_do_not_disturb']}),('AudioPlayback','SetVolume',{'Volume':before['resume_volume']}),('DeviceModes','SetAutoDeepSleep',{'Minutes':before['auto_deep_sleep_minutes']})]:
    try:f(service,name,args)
    except Exception as e:report['cleanup_errors'].append(service+'.'+name+': '+str(e));report['passed']=False
   if a.leave_playing:
    working=next((s for s in report['stations'] if s['passed']),None)
    if working:f('Radio','Play',{'Station':working['id']});wait(lambda s:s['bytes_written']>16000);f('AudioPlayback','SetVolume',{'Volume':min(25,before['resume_volume'])})
   save()
 print(json.dumps({'passed':report['passed'],'stations_verified':sum(s['passed'] for s in report['stations']),'total':len(stations)},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
