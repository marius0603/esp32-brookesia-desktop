"""Start/stop BLE after warm app/audio/sleep cycles, retaining user settings.

This reproduces the pre-controller contiguous-DMA failure, not just cold boot.
No pairing secret is requested or stored. Audio checks run at zero volume.
"""
import argparse,json,time
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'codex-quota-monitor/tools'))
from maintenance_client import SharedPowerDiagnosticClient

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',default='COM5');p.add_argument('--rounds',type=int,default=3);a=p.parse_args()
 assert 1<=a.rounds<=10
 output=ROOT/'codex-quota-monitor/runtime/ble-memory-reuse.json'
 report={'passed':False,'starts':[],'app_checks':[]}
 def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 with SharedPowerDiagnosticClient(a.port,timeout=35) as c:
  c.hello()
  def f(s,n,p=None):return c.call_timeout(s,n,p or {})['result']
  def wait(s,n,predicate,seconds=25):
   end=time.monotonic()+seconds
   while True:
    state=f(s,n)
    if predicate(state):return state
    assert time.monotonic()<end,'State deadline: '+s
    time.sleep(.2)
  mode=f('DeviceModes','GetState');book=f('Audiobook','GetState');phone=f('PhoneProvisioning','GetState')
  assert mode['firmware_version']=='0.8.3-s3.49' and not mode['screen_locked']
  assert not f('ChildMode','GetState')['enabled'],'Do not bypass parent policy for tests'
  assert not book['active'] and not book['sleep_active'] and not f('Radio','GetState')['active'] and not f('VoiceAssistant','GetState')['active']
  assert not phone['active'] and not phone['starting']
  apps=f('SystemCore','ListApps');ids={v['manifest']['id']:v['app_id'] for v in apps}
  songs=f('Audiobook','ListSongs')['tracks'];stories=f('Audiobook','List')['tracks']
  assert len(songs)==20 and len(stories)==30
  for v in apps:
   if v['manifest']['id']!='brookesia.system.super.shell' and v['state'] in ['Running','Paused']:f('SystemCore','StopApp',{'AppId':v['app_id']})
  saved={}
  for path in ['/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json','/sdcard/apps/local.nurserysongs/data/player.json','/sdcard/apps/local.nurserysongs/data/play-mode.json']:
   saved[path]=f('Storage','FSReadText',{'Path':path}) if f('Storage','FSStat',{'Path':path})['exists'] else None
  preservation=ROOT/('codex-quota-monitor/runtime/ble-memory-preserve-'+str(time.time_ns())+'.json')
  preservation.write_text(json.dumps({'files':saved,'modes':mode,'book':book},ensure_ascii=False),encoding='utf-8')
  def open_app(id):
   f('SystemCore','StartApp',{'AppId':ids[id]});v=f('SystemCore','GetActiveApp')
   assert v['app_id']==ids[id] and v['state']=='Running' and not v['last_error'],id
  def start_ble(label):
   f('DeviceModes','Wake');open_app('brookesia.general.settings');before=f('PhoneProvisioning','GetState')
   f('PhoneProvisioning','StartRemote')
   v=wait('PhoneProvisioning','GetState',lambda v:v['active'] or (not v['starting'] and v['start_attempts']>before['start_attempts']))
   assert v['active'],{'label':label,'status':v['status'],'largest':v['start_largest_dma_block'],'free':v['start_dma_free_bytes']}
   assert v['start_largest_dma_block']>=v['required_dma_block'] and v['start_dma_free_bytes']>=40*1024
   assert v['memory_rejections']==phone['memory_rejections']
   report['starts'].append({'label':label,'largest_dma_before':v['start_largest_dma_block'],'dma_free_before':v['start_dma_free_bytes'],'internal_free_active':v['internal_free_bytes'],'largest_dma_active':v['largest_dma_block']});save()
   f('PhoneProvisioning','Stop');wait('PhoneProvisioning','GetState',lambda v:not v['active'] and not v['starting'])
   f('SystemCore','StopApp',{'AppId':ids['brookesia.general.settings']});print(label+' BLE started and closed',flush=True)
  try:
   f('DeviceModes','Wake');f('DeviceModes','SetAutoDeepSleep',{'Minutes':0});f('AudioPlayback','SetVolume',{'Volume':0})
   start_ble('baseline')
   names=['local.flipclock','local.codex.quota','local.weather','local.audiobook','local.nurserysongs','local.radio','local.lightlearning','local.virtualpet','local.voiceassistant','local.childmode']
   for cycle in range(a.rounds):
    for id in names:
     open_app(id);time.sleep(.3);f('SystemCore','StopApp',{'AppId':ids[id]});report['app_checks'].append({'round':cycle+1,'id':id});save()
    start_ble('apps-'+str(cycle+1))
    open_app('local.nurserysongs')
    f('Audiobook','SetSpeed',{'Speed':1});f('Audiobook','Play',{'Path':songs[cycle%len(songs)]['path'],'Position':0})
    wait('Audiobook','GetState',lambda v:v['state']=='Playing' and v['bytes_written']>65536)
    f('Audiobook','TestSleepTimer');wait('Audiobook','GetState',lambda v:v['state']=='SleepEnded' and not v['active'],25)
    f('SystemCore','StopApp',{'AppId':ids['local.nurserysongs']})
    start_ble('sleep-'+str(cycle+1))
   assert f('Audiobook','ListSongs')['tracks']==songs and f('Audiobook','List')['tracks']==stories
   report.update(passed=True,rounds=a.rounds,apps_preserved=len(apps),stories_preserved=len(stories),songs_preserved=len(songs))
  finally:
   cleanup=[]
   steps=[('DeviceModes','Wake',{}),('PhoneProvisioning','Stop',{}),('Audiobook','Stop',{})]
   steps += [('SystemCore','StopApp',{'AppId':ids[id]}) for id in ['local.nurserysongs','local.audiobook','brookesia.general.settings']]
   steps += [('Audiobook','SetSpeed',{'Speed':book['speed']}),('Audiobook','SetSongMode',{'Mode':book['song_play_mode']})]
   for s,n,v in steps:
    try:f(s,n,v)
    except Exception as e:cleanup.append(s+'.'+n+': '+str(e))
   for path,data in saved.items():
    try:
     if data is not None:f('Storage','FSWriteText',{'Path':path,'Data':data})
     elif f('Storage','FSStat',{'Path':path})['exists']:f('Storage','FSRemove',{'Path':path})
    except Exception as e:cleanup.append('restore preference: '+str(e))
   for s,n,v in [('AudioPlayback','SetVolume',{'Volume':mode['resume_volume']}),('DeviceModes','SetAutoDeepSleep',{'Minutes':mode['auto_deep_sleep_minutes']})]:
    try:f(s,n,v)
    except Exception as e:cleanup.append(s+'.'+n+': '+str(e))
   report['volume_restored']=f('DeviceModes','GetState')['resume_volume']==mode['resume_volume']
   report['known_power_dependency_logs']=c.power_dependency_logs;report['cleanup_errors']=cleanup
   report['passed']=report['passed'] and report['volume_restored'] and not cleanup;save()
   assert not cleanup and report['volume_restored'], 'Inspect private cleanup report'
 print('Warm BLE memory checks passed: '+str(len(report['starts']))+' starts after app/audio/sleep cycles',flush=True)

if __name__=='__main__':main()
