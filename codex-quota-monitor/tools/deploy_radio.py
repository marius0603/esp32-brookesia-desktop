"""Install the radio BPK on s3.42+, preserving existing apps and media."""
import argparse,json,time,zipfile,hashlib
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM5');a=p.parse_args()
 package=ROOT/'packages/apps/local.radio.debug.0.1.0.bpk'
 with zipfile.ZipFile(package) as z:
  assert z.testzip() is None
  assert json.loads(z.read('manifest.json'))['package']['id']=='local.radio'
 report={'passed':False,'package_sha256':hashlib.sha256(package.read_bytes()).hexdigest()}
 for attempt in range(3):
  try:
   with StoryClient(a.port,timeout=30) as c:
    c.hello()
    def f(s,n,p=None):return c.call(s,n,p or {})['result']
    mode=f('DeviceModes','GetState');version=mode['firmware_version'].split('-s3.')
    assert len(version)==2 and int(version[-1])>=42,'Install matching s3.42 firmware first'
    story=f('Audiobook','GetState');voice=f('VoiceAssistant','GetState')
    assert not story['active'] and not story['sleep_active'],'Finish the current story and timer first'
    assert not voice.get('recording',False) and not voice.get('active',False),'Finish the current assistant conversation first'
    apps=f('SystemCore','ListApps');tracks=f('Audiobook','List')['tracks'];volume=f('AudioPlayback','GetVolume')
    prior={x['manifest']['id']:x['manifest']['version'] for x in apps if x['manifest']['id']!='local.radio'}
    old=next((x for x in apps if x['manifest']['id']=='local.radio'),None)
    if old:
     f('SystemCore','StopApp',{'AppId':old['app_id']})
     root='/sdcard/apps/local.radio'
     if not f('Storage','FSStat',{'Path':root})['exists']:root='/littlefs/apps/local.radio'
     backup='/sdcard/resource-backups/radio-'+str(int(time.time()))
     f('Storage','FSCopyTree',{'From':root,'To':backup,'Overwrite':False});report['backup']=backup
    result=c.transfer('install_bpk',package,None,False);assert result['ok']
    after=f('SystemCore','ListApps');radio=next(x for x in after if x['manifest']['id']=='local.radio')
    assert {x['manifest']['id']:x['manifest']['version'] for x in after if x['manifest']['id']!='local.radio'}==prior
    assert f('Audiobook','List')['tracks']==tracks and f('AudioPlayback','GetVolume')==volume
    assert radio['manifest']['icon_path'] and radio['manifest']['icon_id']=='launcher_icon'
    report.update(passed=True,radio_app_id=radio['app_id'],icon_path=radio['manifest']['icon_path'],preserved_apps=len(prior),preserved_stories=len(tracks))
   break
  except RuntimeError as exc:
   if attempt==2 or 'Wait timeout after 5000 ms' not in str(exc):raise
   time.sleep(7)
 out=ROOT/'codex-quota-monitor/runtime/radio-deployment.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
