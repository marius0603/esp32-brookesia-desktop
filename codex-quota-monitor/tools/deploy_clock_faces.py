"""Install the three-face clock on SD, preserving other apps and user audio."""
import argparse,json,time,hashlib,zipfile
from pathlib import Path
from maintenance_client import SharedPowerDiagnosticClient
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',default='COM5');a=p.parse_args()
 version=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps']['local.flipclock'];package=ROOT/('packages/apps/local.flipclock.debug.'+version+'.bpk')
 with zipfile.ZipFile(package) as z:assert z.testzip() is None
 report={'passed':False,'version':version,'sha256':hashlib.sha256(package.read_bytes()).hexdigest()}
 with SharedPowerDiagnosticClient(a.port,timeout=35) as c:
  c.hello()
  def f(s,n,a=None):return c.call_timeout(s,n,a or {})['result']
  m=f('DeviceModes','GetState');assert not m['screen_locked']
  for s in ['Audiobook','Radio','VoiceAssistant','LocalVoice']:assert not f(s,'GetState')['active'],'Finish current audio before clock update'
  apps=f('SystemCore','ListApps');old=next(v for v in apps if v['manifest']['id']=='local.flipclock');others={v['manifest']['id']:v['manifest']['version'] for v in apps if v['manifest']['id']!='local.flipclock'}
  f('SystemCore','StopApp',{'AppId':old['app_id']})
  root='/sdcard/apps/local.flipclock'
  if not f('Storage','FSStat',{'Path':root})['exists']:root='/littlefs/apps/local.flipclock'
  backup='/sdcard/resource-backups/clock-faces-'+str(time.time_ns());f('Storage','FSCopyTree',{'From':root,'To':backup,'Overwrite':False});report['backup']=backup
  result=c.transfer('install_bpk',package,'clock-faces-update.bpk',True);assert result['ok'],result
  apps=f('SystemCore','ListApps');clock=next(v for v in apps if v['manifest']['id']=='local.flipclock');assert clock['manifest']['version']==version
  assert {v['manifest']['id']:v['manifest']['version'] for v in apps if v['manifest']['id']!='local.flipclock'}==others
  f('DeviceModes','Wake')
  f('SystemCore','StartApp',{'AppId':clock['app_id']});time.sleep(2)
  active=f('SystemCore','GetActiveApp');assert active['app_id']==clock['app_id'] and active['state']=='Running' and not active['last_error'],active
  assert f('DeviceModes','GetState')['resume_volume']==m['resume_volume']
  report.update(passed=True,apps_preserved=len(apps),volume_preserved=m['resume_volume'])
 (ROOT/'codex-quota-monitor/runtime/clock-faces-deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Three-face clock deployed and opened; other apps/volume preserved',flush=True)
if __name__=='__main__':main()
