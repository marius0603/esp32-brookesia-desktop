"""Check reconstruction of the pinned upstream without touching the worktree."""
import argparse,json,re,subprocess,tempfile,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--upstream-zip',type=Path,required=True);p.add_argument('--compare',type=Path);a=p.parse_args()
    patches=[ROOT/'patches'/n for n in ('brookesia-s3.patch','phone-launcher.patch','desktop-themes.patch','phone-provisioning.patch','phone-remote.patch','bluetooth-settings.patch')]
    paths=set()
    for patch in patches:paths.update(re.findall(r'^\+\+\+ b/(.+)$',patch.read_text(encoding='utf-8'),re.M))
    with tempfile.TemporaryDirectory(prefix='esp32-patch-check-') as name,zipfile.ZipFile(a.upstream_zip) as z:
        base=Path(name);prefix=z.namelist()[0].split('/')[0]+'/'
        for relative in paths:
            assert not PurePosixPath(relative).is_absolute() and '..' not in PurePosixPath(relative).parts
            if prefix+relative in z.namelist():
                target=base/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(prefix+relative))
        for patch in patches:
            normalized=base/('.normalized-'+patch.name)
            normalized.write_bytes(patch.read_text(encoding='utf-8').encode('utf-8'))
            subprocess.run(['git','-c','core.autocrlf=false','apply','--unsafe-paths','--check',str(normalized)],cwd=base,check=True)
            subprocess.run(['git','-c','core.autocrlf=false','apply','--unsafe-paths',str(normalized)],cwd=base,check=True)
        if a.compare:
            for relative in paths:assert (base/relative).read_text(encoding='utf-8')==(a.compare/relative).read_text(encoding='utf-8'),relative
    print('All six patches apply in order; reconstructed',len(paths),'upstream files'+(' and matched the build source.' if a.compare else '.'))
if __name__=='__main__':main()
