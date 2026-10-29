"""Add the phone provisioning card while retaining the installed Wi-Fi screen."""
import argparse,hashlib,json,time
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[2]
TARGET='/littlefs/apps/brookesia.general.settings/res/screens/wifi.json'
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);a=p.parse_args()
 folder=ROOT/'codex-quota-monitor/runtime'/('phone-provisioning-install-'+datetime.now().strftime('%Y%m%d-%H%M%S'));folder.mkdir()
 source=json.loads((ROOT/'packages/resources/phone-provisioning-wifi-s3.32.json').read_text(encoding='utf-8'))
 card=source['children'][0]['children'][0];assert card['id']=='phone_provisioning'
 with StoryClient(a.port,timeout=35) as c:
  c.hello()
  def f(s,n,args=None):return c.call(s,n,args or {})['result']
  modes=f('DeviceModes','GetState');assert not modes['screen_locked'];assert not f('Audiobook','GetState')['sleep_active']
  deadline=time.monotonic()+80
  while True:
   apps=f('SystemCore','ListApps');app=next((x for x in apps if x['manifest']['id']=='brookesia.general.settings'),None)
   if app and any(x['app_id']==1 and x['state']=='Running' for x in apps):break
   assert time.monotonic()<deadline,'Desktop did not finish starting'
   time.sleep(1)
  if app['state'] in ('Running','Paused','Starting'):f('SystemCore','StopApp',{'AppId':app['app_id']})
  # Decode inside the device; compact JSON avoids a large escaped UART reply.
  installed=f('PhoneProvisioning','GetWifiScreen')
  before=json.dumps(installed,ensure_ascii=False,separators=(',',':'))
  (folder/'wifi-before.json').write_text(before,encoding='utf-8')
  backup='/sdcard/resource-backups/'+folder.name+'/wifi.json'
  f('Storage','FSCopyTree',{'From':TARGET,'To':backup,'Overwrite':False})
  doc=json.loads(before);children=doc['children'][0]['children'];children[:]=[v for v in children if v['id']!='phone_provisioning'];children.insert(0,card)
  local=folder/'wifi.json';local.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
  staged=folder.name+'/wifi.json';result=c.transfer('put',local,'sd-themes/'+staged,False)
  assert result['ok'] and result['sha256']==hashlib.sha256(local.read_bytes()).hexdigest()
  f('Storage','FSCopyTree',{'From':'/sdcard/themes/'+staged,'To':TARGET,'Overwrite':True})
  assert json.loads(f('Storage','FSReadText',{'Path':TARGET}))==doc
  f('Storage','FSRemove',{'Path':'/sdcard/themes/'+folder.name})
  report={'passed':True,'backup':backup,'target':TARGET,'bytes':local.stat().st_size,'theme':modes['desktop_theme_index']}
  (folder/'deployment.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
  (ROOT/'codex-quota-monitor/runtime/phone-provisioning-resource-latest.json').write_text(json.dumps({'folder':str(folder)}),encoding='utf-8')
 print('Phone provisioning card installed and read back; existing Wi-Fi screen retained.')
if __name__=='__main__':main()
