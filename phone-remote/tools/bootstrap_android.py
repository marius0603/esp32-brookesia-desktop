"""Fetch pinned official tools into a cache outside the source repository."""
import argparse,hashlib,json,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);a=p.parse_args();cache=a.cache.resolve()
 if cache.is_relative_to(ROOT):raise SystemExit('Keep toolchains and signing keys outside the source repository')
 cache.mkdir(parents=True,exist_ok=True)
 for item in json.loads((Path(__file__).with_name('downloads.json')).read_text()):
  file=cache/item['file']
  if not file.exists() or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:
   temporary=file.with_suffix(file.suffix+'.part')
   with urllib.request.urlopen(item['url'],timeout=120) as source,temporary.open('wb') as target:
    while block:=source.read(1024*1024):target.write(block)
   assert hashlib.sha256(temporary.read_bytes()).hexdigest()==item['sha256'],item['file'];temporary.replace(file)
  if file.suffix=='.zip':
   folder=cache/file.stem;folder.mkdir(exist_ok=True)
   with zipfile.ZipFile(file) as archive:
    for name in archive.namelist():assert (folder/name).resolve().is_relative_to(folder.resolve())
    archive.extractall(folder)
 tools={}
 for key,name,folder in [('java','java.exe','jdk'),('javac','javac.exe','jdk'),('jar','jar.exe','jdk'),('keytool','keytool.exe','jdk'),('android','android.jar','platform'),('aapt2','aapt2.exe','tools'),('d8','d8.jar','tools'),('signer','apksigner.jar','tools')]:tools[key]=str(next((cache/folder).rglob(name)))
 tools['bc']=str(cache/'bcprov.jar');(cache/'tools.json').write_text(json.dumps(tools,indent=2)+'\n');print('Android tools verified; configuration:',cache/'tools.json')
if __name__=='__main__':main()
