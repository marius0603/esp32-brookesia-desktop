"""Export only development sources and reviewed packages into a portable repository."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT.parent/'esp32-brookesia-desktop'
UPSTREAM=ROOT.parent/'esp-brookesia-v08'
PROJECT=UPSTREAM/'examples/system/super_s3_216'
COMMIT='68ac00e7aa9012cd8cbf0cbf6bee155801db0e8c'
if DEST.exists():raise SystemExit(f'Export destination already exists: {DEST}')
DEST.mkdir()
excluded={'.git','.venv','__pycache__','node_modules','build','managed_components','runtime','vendor','.cache'}
def copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
def tree(source,target):
    for p in source.rglob('*'):
        rel=p.relative_to(source)
        if p.is_file() and not any(v in excluded for v in rel.parts) and not p.name.endswith(('.pyc','.old','.partial')):
            copy(p,target/rel)
computer=DEST/'codex-quota-monitor'
for p in ROOT.iterdir():
    if p.is_file() and p.suffix in ('.md','.ps1','.cmd','.txt','.json') and p.name!='config.json':copy(p,computer/p.name)
for folder in ('quota_monitor','tests','firmware','brookesia'):
    tree(ROOT/folder,computer/folder)
for p in (ROOT/'tools').iterdir():
    if p.is_file() and p.suffix in ('.py','.ps1','.patch'):copy(p,computer/'tools'/p.name)
for folder in ('font-converter','brookesia-toolkit'):
    for p in (ROOT/'tools'/folder).iterdir():
        if p.is_file() and (p.suffix=='.json' or p.name.endswith('lock.yaml')):copy(p,computer/'tools'/folder/p.name)
# Keep the official USB client source at its pinned version, available before cloning the SDK.
tree(UPSTREAM/'tools/brookesia_usb',computer/'vendor-source/brookesia-usb')
(computer/'requirements.txt').write_text('pyserial==3.5\n-e ./vendor-source/brookesia-usb\n',encoding='utf-8')
config=json.loads((ROOT/'config.json').read_text(encoding='utf-8'));config['serial_port']='auto'
for name in ('config.json','config.example.json'):(computer/name).write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
versions={}
for app in (ROOT.parent/'brookesia-apps').iterdir():
    if not app.is_dir():continue
    dest=DEST/'brookesia-apps'/app.name
    for folder in ('src','tests','tools','assets'):
        if (app/folder).exists():tree(app/folder,dest/folder)
    for name in ('package.json','brookesia.config.js','preview.png'):
        if (app/name).exists():copy(app/name,dest/name)
    manifest=json.loads((app/'src/manifest.json').read_text(encoding='utf-8'))['package']
    versions[manifest['id']]=manifest['version']
    bpk=app/'dist'/f"{manifest['id']}.debug.{manifest['version']}.bpk"
    copy(bpk,DEST/'packages/apps'/bpk.name)
platform=DEST/'platform/super_s3_216'
for folder in ('main','tools','components'):
    tree(PROJECT/folder,platform/folder)
for p in PROJECT.iterdir():
    if p.is_file() and p.name not in ('sdkconfig','sdkconfig.old','.gitignore'):copy(p,platform/p.name)
copy(PROJECT/'sdkconfig',platform/'sdkconfig.reproducible')
# Keep the exact fonts needed for a first firmware build; GUI app resources are staged by CMake.
tree(PROJECT/'littlefs/system/fonts',platform/'littlefs/system/fonts')
for p in PROJECT.rglob('.gitkeep'):
    if not any(v in excluded for v in p.relative_to(PROJECT).parts):copy(p,platform/p.relative_to(PROJECT))
patch=subprocess.check_output(['git','diff','--binary','--ignore-space-at-eol',COMMIT,'--'],cwd=UPSTREAM)
(DEST/'patches').mkdir();(DEST/'patches/brookesia-s3.patch').write_bytes(patch)
copy(UPSTREAM/'license.txt',DEST/'UPSTREAM_LICENSE')
copy(PROJECT/'build/brookesia_s3_216.bin',DEST/'packages/firmware/brookesia-0.8.3-s3.3-app.bin')
copy(PROJECT/'build/partition_table/partition-table.bin',DEST/'packages/firmware/partition-table.bin')
metadata={'upstream':'https://github.com/espressif/esp-brookesia.git','commit':COMMIT,'esp_idf':'6.0.2',
          'firmware':'0.8.3-s3.3','toolkit':'1.0.1','apps':versions,'device':'ESP32-S3-Touch-AMOLED-2.16'}
(DEST/'versions.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
checksums={p.relative_to(DEST).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (DEST/'packages').rglob('*') if p.is_file()}
(DEST/'packages/SHA256.json').write_text(json.dumps(checksums,indent=2)+'\n',encoding='utf-8')
print(DEST)
print(json.dumps({'files':sum(p.is_file() for p in DEST.rglob('*')),'apps':versions}))
