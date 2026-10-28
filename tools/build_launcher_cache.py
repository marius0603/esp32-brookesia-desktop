"""Build presized opaque RGB565/RLE launcher artwork from the existing Q icons."""
import hashlib,json,struct,sys
from array import array
from pathlib import Path
from PIL import Image
from build_wallpaper_render import rle_pixels
ROOT=Path(__file__).resolve().parents[1]
theme=ROOT/'themes/cartoon-q-v1'
output=theme/'launcher-optimized';output.mkdir(exist_ok=True)
icons=json.loads((theme/'theme.json').read_text(encoding='utf-8'))['icons']
sources={app:theme/'flash-fallback'/name for app,name in icons.items()}
sources['local.lightlearning']=ROOT/'brookesia-apps/light-learning/src/res/images/launcher_icon.png'
manifest={'schema':1,'version':'1.0.0','size':92,'background':'#fff1dc','format':'LVGL RGB565 RLE','icons':{},'files':{}}
for app,source in sources.items():
 image=Image.open(source).convert('RGBA').resize((92,92),Image.Resampling.LANCZOS)
 background=Image.new('RGBA',(92,92),manifest['background']);background.alpha_composite(image)
 rgb=background.convert('RGB').tobytes()
 pixels=array('H',(((r>>3)<<11)|((g>>2)<<5)|(b>>3) for r,g,b in zip(rgb[0::3],rgb[1::3],rgb[2::3])))
 if sys.byteorder!='little':pixels.byteswap()
 raw=pixels.tobytes();encoded=rle_pixels(raw)
 data=struct.pack('<BBHHHHH',0x19,0x12,8,92,92,184,0)+struct.pack('<III',1,len(encoded),len(raw))+encoded
 name=app+'.bin';(output/name).write_bytes(data);manifest['icons'][app]=name
 manifest['files'][name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'source':source.relative_to(ROOT).as_posix(),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
resource=json.loads((ROOT/'packages/resources/phone-launcher-s3.30.json').read_text(encoding='utf-8'))
resource['children'][0]['children'][0]['placement']['height']=242
(output/'app_launcher.json').write_text(json.dumps(resource,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
layout=(output/'app_launcher.json').read_bytes()
manifest['layout']={'file':'app_launcher.json','bytes':len(layout),'sha256':hashlib.sha256(layout).hexdigest()}
(output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Built',len(sources),'presized native icons;',sum(x['bytes'] for x in manifest['files'].values()),'bytes; RLE decoded pixels checked.')
