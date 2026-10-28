"""Back up and install the launcher document required by s3.28 before updating the app partition."""
import argparse,json
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--port',required=True)
p.add_argument('--source',type=Path,help='Optional patched ESP-Brookesia checkout; otherwise use the reviewed release document')
a=p.parse_args()
source=(a.source/'system/brookesia_system_super/resource/shell/screens/app_launcher.json') if a.source else ROOT.parent/'packages/resources/phone-launcher-s3.28.json'
doc=json.loads(source.read_text(encoding='utf-8'))
data=json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n'
content=doc['children'][0];assert any(n['id']=='pages' for n in content['children'])
assert not content['children'][0]['commonProps']['scrollable']
remote='/littlefs/system/super/shell/screens/app_launcher.json'
backup=ROOT/'runtime'/('phone-launcher-'+datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir()
with StoryClient(a.port,timeout=30) as c:
 c.hello()
 def call(s,f,args=None):return c.call(s,f,args or {})['result']
 before=call('Storage','FSReadText',{'Path':remote})
 (backup/'app_launcher.json').write_text(before,encoding='utf-8')
 snapshot={'volume':call('AudioPlayback','GetVolume'),'tracks':call('Audiobook','List')['tracks']}
 (backup/'preservation.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
 call('Storage','FSWriteText',{'Path':remote,'Data':data})
 assert call('Storage','FSReadText',{'Path':remote})==data
 print('Launcher document verified. Private backup:',backup)
 print('Update the matching firmware application and restart to load this layout.')
