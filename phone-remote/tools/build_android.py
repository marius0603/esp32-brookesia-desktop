"""Build the small Java BLE app with an external JDK and Android build-tools."""
import argparse,json,subprocess,zipfile,hashlib,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--tools',type=Path,required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args()
 t=json.loads(a.tools.read_text());w=a.work.resolve()
 if w.is_relative_to(ROOT):raise SystemExit('Keep generated classes and the signing key outside the source repository')
 w.mkdir(parents=True,exist_ok=True)
 def run(*cmd):subprocess.run([str(x) for x in cmd],check=True)
 classes=w/'classes';classes.mkdir(exist_ok=True);dex=w/'dex';dex.mkdir(exist_ok=True)
 sources=sorted((ROOT/'phone-remote/android/src').rglob('*.java'))
 run(t['javac'],'-encoding','UTF-8','-source','8','-target','8','-classpath',t['android']+os.pathsep+t['bc'],'-d',classes,*sources)
 jar=w/'app.jar';run(t['jar'],'cf',jar,'-C',classes,'.')
 run(t['java'],'-Xmx3g','-cp',t['d8'],'com.android.tools.r8.D8','--lib',t['android'],'--min-api','26','--output',dex,jar,t['bc'])
 unsigned=w/'unsigned.apk';run(t['aapt2'],'link','-I',t['android'],'--manifest',ROOT/'phone-remote/android/AndroidManifest.xml','-o',unsigned)
 with zipfile.ZipFile(unsigned,'a',compression=zipfile.ZIP_DEFLATED) as z:
  for file in sorted(dex.glob('*.dex')):z.write(file,file.name)
  for file in sorted((ROOT/'phone-remote/licenses').glob('*.txt')):z.write(file,'assets/licenses/'+file.name)
 key=w/'development-signing.jks'
 if not key.exists():run(t['keytool'],'-genkeypair','-keystore',key,'-storepass','android','-keypass','android','-alias','xiaoma','-keyalg','RSA','-keysize','3072','-validity','3650','-dname','CN=XiaoMa Remote Development')
 output=ROOT/'packages/android/xiaoma-remote-0.1.0.apk';output.parent.mkdir(parents=True,exist_ok=True)
 run(t['java'],'-jar',t['signer'],'sign','--v4-signing-enabled','false','--ks',key,'--ks-pass','pass:android','--out',output,unsigned)
 run(t['java'],'-jar',t['signer'],'verify','--verbose',output)
 hashes=ROOT/'packages/SHA256.json';doc=json.loads(hashes.read_text());doc[output.relative_to(ROOT).as_posix()]=hashlib.sha256(output.read_bytes()).hexdigest();hashes.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Android remote APK:',output)
if __name__=='__main__':main()
