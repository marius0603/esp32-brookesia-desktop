"""Build a private, Key-bearing navigation APK; refuse repository output paths."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[2]
ANDROID='{http://schemas.android.com/apk/res/android}'
ET.register_namespace('android',ANDROID[1:-1])


def external(path):
 path=Path(path).resolve()
 if path.is_relative_to(ROOT):raise ValueError('Private trial inputs and output must remain outside Git')
 return path


def trial_manifest(key):
 if not re.fullmatch(r'[0-9a-fA-F]{32}',key):raise ValueError('Invalid Android Key format')
 tree=ET.parse(ROOT/'phone-remote/android/AndroidManifest.xml');root=tree.getroot()
 root.set(ANDROID+'versionCode','10');root.set(ANDROID+'versionName','0.4.2-trial')
 permissions={n.get(ANDROID+'name'):n for n in root.findall('uses-permission')}
 for name in ('INTERNET','ACCESS_NETWORK_STATE','ACCESS_WIFI_STATE','ACCESS_FINE_LOCATION','ACCESS_COARSE_LOCATION'):
  full='android.permission.'+name
  node=permissions.get(full)
  if node is None:node=ET.SubElement(root,'uses-permission',{ANDROID+'name':full})
  node.attrib.pop(ANDROID+'maxSdkVersion',None)
 app=root.find('application')
 ET.SubElement(app,'meta-data',{ANDROID+'name':'com.amap.api.v2.apikey',ANDROID+'value':key})
 ET.SubElement(app,'meta-data',{ANDROID+'name':'xiaoma.navigation_trial',ANDROID+'value':'true'})
 ET.SubElement(app,'activity',{ANDROID+'name':'.NavigationTrialActivity',ANDROID+'exported':'false'})
 ET.SubElement(app,'service',{ANDROID+'name':'com.amap.api.location.APSService',ANDROID+'exported':'false',ANDROID+'foregroundServiceType':'location'})
 return tree


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('tools','work','key-file','sdk-libs','keystore','output'):parser.add_argument('--'+name,type=Path,required=True)
 a=parser.parse_args();work=external(a.work);output=external(a.output);key_file=external(a.key_file);keystore=external(a.keystore)
 manifest=trial_manifest(key_file.read_text(encoding='utf-8-sig').strip())
 config=json.loads((ROOT/'phone-remote/amap-sdk.json').read_text(encoding='utf-8'));libs=a.sdk_libs.resolve()
 for name,digest in config['files'].items():
  assert hashlib.sha256((libs/name).read_bytes()).hexdigest()==digest,'SDK file verification failed: '+name
 tools=json.loads(a.tools.read_text(encoding='utf-8'));jar=next(libs.glob('*.jar'))
 work.mkdir(parents=True,exist_ok=True);classes=work/'classes';classes.mkdir(exist_ok=True);dex=work/'dex';dex.mkdir(exist_ok=True)
 def run(*cmd):subprocess.run([str(x) for x in cmd],check=True)
 probe=work/'sdk-api-check';probe.mkdir(exist_ok=True)
 run(tools['javac'],'-encoding','UTF-8','-classpath',str(tools['android'])+';'+str(jar),'-d',probe,ROOT/'phone-remote/tests/NavigationSdkApiProbe.java')
 sources=sorted((ROOT/'phone-remote/android/src').rglob('*.java'))
 run(tools['javac'],'-encoding','UTF-8','-source','8','-target','8','-classpath',str(tools['android'])+';'+str(tools['bc']),'-d',classes,*sources)
 application=work/'app.jar';run(tools['jar'],'cf',application,'-C',classes,'.')
 run(tools['java'],'-Xmx3g','-cp',tools['d8'],'com.android.tools.r8.D8','--lib',tools['android'],'--min-api','26','--output',dex,application,tools['bc'],jar)
 resources=work/'launcher-resources.zip';run(tools['aapt2'],'compile','--dir',ROOT/'phone-remote/android/res','-o',resources)
 private_manifest=work/'AndroidManifest.xml';manifest.write(private_manifest,encoding='utf-8',xml_declaration=True)
 unsigned=work/'unsigned.apk';run(tools['aapt2'],'link','-I',tools['android'],'--manifest',private_manifest,'-R',resources,'--auto-add-overlay','-o',unsigned)
 with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as z:
  for path in sorted(dex.glob('*.dex')):z.write(path,path.name)
  for name in config['files']:
   if name.startswith('arm64-v8a/') and name.endswith('.so'):z.write(libs/name,'lib/'+name)
  with zipfile.ZipFile(jar) as sdk:
   for name in sdk.namelist():
    if name.startswith('assets/') and not name.endswith('/'):z.writestr(name,sdk.read(name))
  for path in (ROOT/'phone-remote/licenses').glob('*.txt'):z.write(path,'assets/licenses/'+path.name)
 candidate=work/'signed-candidate.apk'
 run(tools['java'],'-jar',tools['signer'],'sign','--v4-signing-enabled','false','--ks',keystore,'--ks-pass','pass:android','--out',candidate,unsigned)
 proof=subprocess.check_output([tools['java'],'-jar',tools['signer'],'verify','--print-certs',str(candidate)],text=True,encoding='utf-8')
 certificate=re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-fA-F]+)',proof).group(1).lower()
 expected=json.loads((ROOT/'phone-remote/signing/manifest.json').read_text(encoding='utf-8'))['apk_signer_certificate_sha256']
 assert certificate==expected,'Original certificate mismatch; refusing to publish trial'
 output.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(candidate,output)
 with zipfile.ZipFile(output) as z:
  assert z.testzip() is None
  assert any(n.startswith('lib/arm64-v8a/') for n in z.namelist())
 (work/'build-report.json').write_text(json.dumps({'passed':True,'version':'0.4.2-trial','certificate_matches':True,'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'private_output':str(output)},indent=2),encoding='utf-8')
 print('Private trial APK built; original signing certificate verified. Key not printed.')
 print(output)


if __name__=='__main__':main()
