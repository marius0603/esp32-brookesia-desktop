"""Download the pinned official SDK without accessing any user Key or API."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile
ROOT=Path(__file__).resolve().parents[2]


def main():
 p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);a=p.parse_args()
 base=a.cache.resolve();assert not base.is_relative_to(ROOT),'SDK cache must be outside Git'
 base.mkdir(parents=True,exist_ok=True);config=json.loads((ROOT/'phone-remote/amap-sdk.json').read_text(encoding='utf-8'))
 bundle=base/'AMap_Android_Navi_SDK_All.zip'
 if not bundle.exists():
  temporary=base/'sdk-download.tmp'
  with urllib.request.urlopen(config['download_url'],timeout=30) as response,temporary.open('wb') as out:
   while chunk:=response.read(1024*1024):out.write(chunk)
  assert hashlib.sha256(temporary.read_bytes()).hexdigest()==config['bundle_sha256'],'Official download changed; refusing unpinned SDK'
  temporary.rename(bundle)
 assert hashlib.sha256(bundle.read_bytes()).hexdigest()==config['bundle_sha256']
 with zipfile.ZipFile(bundle) as outer:
  data=outer.read('AMap3DMap_AMapNavi_AMapSearch_AMapLocation.zip')
  assert hashlib.md5(data).hexdigest()==config['inner_zip_md5'],'Official SDK package MD5 mismatch'
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   for name,digest in config['files'].items():
    content=z.read(name);assert hashlib.sha256(content).hexdigest()==digest
    target=base/'libs'/name;assert target.resolve().is_relative_to((base/'libs').resolve())
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
 print('Pinned SDK and arm64 libraries ready. No provider API requests were made.')


if __name__=='__main__':main()
