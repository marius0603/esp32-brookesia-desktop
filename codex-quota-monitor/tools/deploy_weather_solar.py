"""Update only weather script/manifest and preserve all installed theme resources."""
import argparse,hashlib,json,time,zipfile
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);a=p.parse_args()
 stamp=datetime.now().strftime('%Y%m%d-%H%M%S');folder=ROOT/'codex-quota-monitor/runtime'/('weather-solar-'+stamp);folder.mkdir()
 backup='/sdcard/resource-backups/weather-solar-'+stamp
 with zipfile.ZipFile(ROOT/'packages/apps/local.weather.debug.0.2.7.bpk') as z:files={n:z.read(n) for n in ('app/main.js','manifest.json')}
 report={'passed':False,'backup':backup,'files':{}}
 with StoryClient(a.port,timeout=30) as c:
  c.hello()
  def f(s,n,p=None):return c.call(s,n,p or {})['result']
  apps=f('SystemCore','ListApps');app=next(x for x in apps if x['manifest']['id']=='local.weather')
  assert not f('Audiobook','GetState')['sleep_active'],'Do not interrupt a sleep timer'
  f('SystemCore','StopApp',{'AppId':app['app_id']})
  icon='/littlefs/apps/local.weather/res/images/index.json';saved_icon=f('Storage','FSReadText',{'Path':icon})
  for n in files:
   f('Storage','FSCopyTree',{'From':'/littlefs/apps/local.weather/'+n,'To':backup+'/'+Path(n).name,'Overwrite':False})
  try:
   for n,data in files.items():
    target='/littlefs/apps/local.weather/'+n
    local=folder/(Path(n).name+'.bin');local.write_bytes(data)
    dest='sd-themes/weather-solar-'+stamp+'/'+local.name
    result=c.transfer('put',local,dest,False);digest=hashlib.sha256(data).hexdigest();assert result['ok'] and result['sha256']==digest
    f('Storage','FSCopyTree',{'From':'/sdcard/themes/weather-solar-'+stamp+'/'+local.name,'To':target,'Overwrite':True})
    for _ in range(20):
     if hashlib.sha256(f('Storage','FSReadText',{'Path':target}).encode('utf-8')).hexdigest()==digest:break
     time.sleep(.1)
    else:raise AssertionError('Installed weather file hash differs: '+n)
    report['files'][n]=digest
  except Exception:
   for n in files:f('Storage','FSCopyTree',{'From':backup+'/'+Path(n).name,'To':'/littlefs/apps/local.weather/'+n,'Overwrite':True})
   raise
  assert f('Storage','FSReadText',{'Path':icon})==saved_icon
  report['passed']=True
 (folder/'deployment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print('Installed weather0.2.7 script and manifest; original transparent launcher index preserved. Restart to refresh version metadata.')
if __name__=='__main__':main()
