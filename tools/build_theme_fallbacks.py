"""Export compact Flash icon copies; artwork stays unchanged."""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--theme',type=Path,default=ROOT/'themes/cream-handdrawn-v1');parser.add_argument('--size',type=int,choices=(64,96),default=96);parser.add_argument('--colors',type=int,default=64);args=parser.parse_args()
    assert 16<=args.colors<=256
    output=args.theme/'flash-fallback';output.mkdir(exist_ok=True)
    manifest=json.loads((args.theme/'theme.json').read_text(encoding='utf-8'));files={}
    for name in manifest['icons'].values():
        target=output/name
        with Image.open(args.theme/name) as image:
            image=image.convert('RGBA')
            if image.size!=(args.size,args.size):image=image.resize((args.size,args.size),Image.Resampling.LANCZOS)
            image.quantize(colors=args.colors,method=Image.Quantize.FASTOCTREE,dither=Image.Dither.NONE).save(target,optimize=True)
        files[name]={'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    (output/'manifest.json').write_text(json.dumps({'files':files},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(files),'bytes':sum(v['bytes'] for v in files.values())}))
if __name__=='__main__':main()
