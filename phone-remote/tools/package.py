"""Verify and hash the paired firmware, Android APK and Settings document."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 fw='packages/firmware/brookesia-0.8.3-s3.33-app-only.zip';apk='packages/android/xiaoma-remote-0.1.0.apk';ui='packages/resources/phone-remote-wifi-s3.33.json';resource='packages/resources/phone-remote-s3.33.zip'
 with zipfile.ZipFile(ROOT/fw) as z:
  m=json.loads(z.read('manifest.json'));assert m['features']['phone_ble_remote'] and m['features']['ble_controller_flash_code']
  for name,meta in m['files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==meta['sha256']
 with zipfile.ZipFile(ROOT/apk) as z:assert 'classes.dex' in z.namelist() and 'assets/licenses/bouncycastle.txt' in z.namelist() and z.testzip() is None
 with zipfile.ZipFile(ROOT/resource,'w',zipfile.ZIP_DEFLATED) as z:
  z.write(ROOT/ui,'wifi.json');z.write(ROOT/'phone-remote/README.md','README.md')
 p=ROOT/'packages/SHA256.json';hashes=json.loads(p.read_text())
 for name in [fw,apk,ui,resource]:hashes[name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
 p.write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Paired BLE remote firmware, APK and UI packages verified.')
if __name__=='__main__':main()
