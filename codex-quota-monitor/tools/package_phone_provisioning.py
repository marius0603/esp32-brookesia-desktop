"""Package public phone provisioning UI resources and record the matching firmware."""
import hashlib,json,zipfile
from pathlib import Path
from build_learning_packages import archive
ROOT=Path(__file__).resolve().parents[2]
def main():
 resource=ROOT/'packages/resources/phone-provisioning-wifi-s3.32.json'
 doc=json.loads(resource.read_text(encoding='utf-8'));card=doc['children'][0]['children'][0]
 assert card['id']=='phone_provisioning' and card['children'][2]['events'][0]['action']=='settings.wifi.phone_provisioning'
 source={'wifi.json':resource.read_bytes(),'PHONE_PROVISIONING.md':(ROOT/'codex-quota-monitor/PHONE_PROVISIONING.md').read_bytes()}
 name='packages/resources/phone-provisioning-s3.32.zip';digest=archive(ROOT/name,source)
 p=ROOT/'packages/SHA256.json';hashes=json.loads(p.read_text(encoding='utf-8'));hashes[name]=digest
 firmware='packages/firmware/brookesia-0.8.3-s3.32-app-only.zip'
 with zipfile.ZipFile(ROOT/firmware) as z:
  manifest=json.loads(z.read('manifest.json'));assert manifest['features']['phone_ble_provisioning']
  for name,meta in manifest['files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==meta['sha256']
 hashes[firmware]=hashlib.sha256((ROOT/firmware).read_bytes()).hexdigest()
 hashes[resource.relative_to(ROOT).as_posix()]=hashlib.sha256(resource.read_bytes()).hexdigest()
 p.write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Phone provisioning UI and matching app-only firmware packages verified.')
if __name__=='__main__':main()
