"""Merge the Bluetooth root entry and dedicated screen, preserving other settings."""
import argparse,json,sys,time
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'codex-quota-monitor/tools'))
from deploy_audiobook_sleep import StoryClient
def find(node,id):
 if isinstance(node,dict):
  if node.get('id')==id:return node
  for value in node.values():
   if (result:=find(value,id)) is not None:return result
 elif isinstance(node,list):
  for value in node:
   if (result:=find(value,id)) is not None:return result
 return None
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);a=p.parse_args();folder=ROOT/'codex-quota-monitor/runtime'/('bluetooth-settings-'+datetime.now().strftime('%Y%m%d-%H%M%S'));folder.mkdir();base='/littlefs/apps/brookesia.general.settings/res/';source=ROOT/'packages/resources/bluetooth-settings-s3.34'
 names=['screens/settings_home.json','flows/content.json','screens/wifi.json','screens/bluetooth.json','root.json']
 with StoryClient(a.port,timeout=30) as c:
  c.hello()
  def f(s,n,args=None):return c.call(s,n,args or {})['result']
  deadline=time.monotonic()+90
  while True:
   apps=f('SystemCore','ListApps');settings=next((x for x in apps if x['manifest']['id']=='brookesia.general.settings'),None)
   if settings and len(apps)>=12:break
   assert time.monotonic()<deadline;time.sleep(1)
  if settings['state'] in ('Running','Paused','Starting'):f('SystemCore','StopApp',{'AppId':settings['app_id']})
  docs={}
  for name in names:
   if f('Storage','FSStat',{'Path':base+name})['exists']:
    old=f('PhoneProvisioning','GetWifiScreen',{'Document':name});backup=folder/name;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_text(json.dumps(old,ensure_ascii=False),encoding='utf-8');f('Storage','FSCopyTree',{'From':base+name,'To':'/sdcard/resource-backups/'+folder.name+'/'+name,'Overwrite':False});docs[name]=old
  root=docs['root.json'];root['assets']=[x for x in root['assets'] if x!='screens/bluetooth.json'];root['assets'].insert(root['assets'].index('screens/wifi.json')+1,'screens/bluetooth.json')
  flow=docs['flows/content.json'];flow['screens']=[x for x in flow['screens'] if x!='bluetooth']+['bluetooth'];flow['transitions']=[x for x in flow['transitions'] if x['action']!='settings.open.bluetooth']+[{'from':[],'action':'settings.open.bluetooth','to':'bluetooth'}]
  row=find(json.loads((source/'screens/settings_home.json').read_text(encoding='utf-8')),'bluetooth');rows=find(docs['screens/settings_home.json'],'main_list')['slots']['content'];rows[:]=[x for x in rows if x['id']!='bluetooth'];index=next(i for i,x in enumerate(rows) if x['id']=='wifi');rows.insert(index+1,row)
  card=find(docs['screens/wifi.json'],'phone_provisioning')
  if card:card['children']=[x for x in card['children'] if x['id']!='remote'];card['children'][0]['labelProps']['text']='手机配网';card['placement']['height']=222
  docs['screens/bluetooth.json']=json.loads((source/'screens/bluetooth.json').read_text(encoding='utf-8'))
  for name in names:
   local=folder/('install-'+name.replace('/','-'));local.write_text(json.dumps(docs[name],ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8');stage=folder.name+'/'+name
   assert c.transfer('put',local,'sd-themes/'+stage,False)['ok'];f('Storage','FSCopyTree',{'From':'/sdcard/themes/'+stage,'To':base+name,'Overwrite':True});assert f('PhoneProvisioning','GetWifiScreen',{'Document':name})==docs[name]
  f('Storage','FSRemove',{'Path':'/sdcard/themes/'+folder.name})
 print('Bluetooth entry is next to Wi-Fi; all five documents read back. Reboot required to invalidate preloaded Settings DOM.')
if __name__=='__main__':main()
