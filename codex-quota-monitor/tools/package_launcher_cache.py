"""Package the reproducible optimized launcher resources without runtime data."""
import hashlib,json
from pathlib import Path
from build_learning_packages import archive
ROOT=Path(__file__).resolve().parents[2]
source=ROOT/'themes/cartoon-q-v1/launcher-optimized'
manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
files={name:(source/name).read_bytes() for name in manifest['files']}
for name,data in files.items():assert hashlib.sha256(data).hexdigest()==manifest['files'][name]['sha256']
files['app_launcher.json']=(source/'app_launcher.json').read_bytes()
assert hashlib.sha256(files['app_launcher.json']).hexdigest()==manifest['layout']['sha256']
files['manifest.json']=(source/'manifest.json').read_bytes()
files['README.txt']=b'Optimized Q launcher resources 1.0.0 for firmware s3.30.\nUse tools/deploy_launcher_cache.py from the matching repository, then restart.\nPreserves apps, stories and volume; backs up original launcher resources privately.\nRestore with --restore <first backup folder>, then restart.\n'
name='packages/resources/launcher-optimized-'+manifest['version']+'.zip'
checksum=archive(ROOT/name,files)
p=ROOT/'packages/SHA256.json';hashes=json.loads(p.read_text(encoding='utf-8'));hashes[name]=checksum;p.write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Optimized launcher package verified:',name,checksum)
