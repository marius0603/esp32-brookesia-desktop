"""Measure real app startup/close latency without changing parent controls."""
import argparse,json,time,statistics
from pathlib import Path
from maintenance_client import MaintenanceClient
ROOT=Path(__file__).resolve().parents[2]

def main():
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM5');p.add_argument('--output',type=Path,required=True);p.add_argument('--rounds',type=int,default=2);a=p.parse_args()
 ids=['local.flipclock','local.codex.quota','local.weather','local.audiobook','local.radio','local.lightlearning','local.virtualpet','local.voiceassistant']
 result={'passed':False,'samples':[]}
 def save():a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 with MaintenanceClient(a.port,timeout=40) as c:
  c.hello()
  def f(s,n,p=None):return c.call(s,n,p or {})['result']
  mode=f('DeviceModes','GetState');assert not mode['screen_locked'];assert not f('Audiobook','GetState')['active'] and not f('Radio','GetState')['active'] and not f('VoiceAssistant','GetState')['active'],'Finish current audio before benchmarking'
  result['firmware']=mode['firmware_version'];apps=f('SystemCore','ListApps');catalog={x['manifest']['id']:x['app_id'] for x in apps}
  for app in apps:
   if app['manifest']['id']!='brookesia.system.super.shell' and app['state'] in ('Running','Paused'):f('SystemCore','StopApp',{'AppId':app['app_id']})
  f('DeviceModes','Wake');f('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
  try:
   for cycle in range(a.rounds):
    for name in ids:
     assert name in catalog,name
     start=time.perf_counter();f('SystemCore','StartApp',{'AppId':catalog[name]});opened=time.perf_counter()-start
     active=f('SystemCore','GetActiveApp');assert active['app_id']==catalog[name] and active['state']=='Running' and not active['last_error'],active
     time.sleep(.45);start=time.perf_counter();f('SystemCore','StopApp',{'AppId':catalog[name]});closed=time.perf_counter()-start
     result['samples'].append({'id':name,'round':cycle+1,'start_seconds':round(opened,4),'close_seconds':round(closed,4)});save();print(name,round(opened,3),round(closed,3),flush=True);time.sleep(.25)
   result['medians']={name:{k:round(statistics.median(x[k] for x in result['samples'] if x['id']==name),4) for k in ['start_seconds','close_seconds']} for name in ids}
   result['passed']=True
  finally:f('DeviceModes','SetAutoDeepSleep',{'Minutes':mode['auto_deep_sleep_minutes']});save()
 print('Startup benchmark passed',flush=True)
if __name__=='__main__':main()
