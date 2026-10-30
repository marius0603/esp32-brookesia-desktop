"""Reconstruct the exact upstream revision and apply this repository's S3 adaptation."""
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
VERSIONS=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))
REPO=ROOT/'esp-brookesia-v08'
def git(*args,check=True):
    return subprocess.run(['git','-c','core.longpaths=true',*args],cwd=REPO,check=check)

if not (REPO/'.git').exists():
    if REPO.exists() and any(REPO.iterdir()):raise SystemExit('Upstream folder is not an empty Git checkout')
    REPO.mkdir(exist_ok=True)
    git('init')
    git('config','core.autocrlf','false')
    git('remote','add','origin',VERSIONS['upstream'])
    git('fetch','--depth=1','origin',VERSIONS['commit'])
    git('checkout','--detach','FETCH_HEAD')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
if head!=VERSIONS['commit']:raise SystemExit('Upstream revision differs; refusing to alter your checkout')
for name in ('brookesia-s3.patch','phone-launcher.patch','desktop-themes.patch','phone-provisioning.patch','phone-remote.patch','bluetooth-settings.patch','remote-navigation.patch'):
    patch=ROOT/'patches'/name
    if git('apply','--check',str(patch),check=False).returncode==0:
        git('apply',str(patch))
    elif git('apply','--reverse','--check',str(patch),check=False).returncode!=0:
        raise SystemExit('Patch conflicts with local changes; preserve and inspect your checkout: '+name)
source=ROOT/'platform/super_s3_216'
target=REPO/'examples/system/super_s3_216'
for path in source.rglob('*'):
    if not path.is_file():continue
    relative=path.relative_to(source)
    out=target/relative
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists() and out.read_bytes()!=path.read_bytes():
        raise SystemExit(f'Existing file differs; not overwriting: {out}')
    if not out.exists():shutil.copy2(path,out)
if not (target/'sdkconfig').exists():shutil.copy2(source/'sdkconfig.reproducible',target/'sdkconfig')
(ROOT/'codex-quota-monitor/runtime').mkdir(exist_ok=True)
print('Workspace ready:',target)
print('Next: install Python/Node dependencies; firmware toolchain is optional for app-only work.')
