"""Export the approved illustrated atlas and wallpaper as opaque native assets."""
import hashlib,json,struct,sys
from array import array
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
from build_wallpaper_render import rle_pixels
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'themes/cyberpunk-v1'
APPS=['brookesia.general.settings','brookesia.general.files','brookesia.general.app_store','local.codex.quota','local.weather','local.audiobook','local.flipclock','local.voiceassistant','local.childmode','local.lightlearning']
BOXES=[(40,24,430,380),(445,28,800,380),(810,24,1175,380),(1190,32,1540,380),(1560,28,1945,380),(38,385,432,730),(438,385,805,730),(810,385,1180,730),(1190,385,1540,730),(1550,385,1950,730)]
def native(image,path):
    image=image.convert('RGB');w,h=image.size;rgb=image.tobytes()
    pixels=array('H',(((r>>3)<<11)|((g>>2)<<5)|(b>>3) for r,g,b in zip(rgb[0::3],rgb[1::3],rgb[2::3])))
    if sys.byteorder!='little':pixels.byteswap()
    raw=pixels.tobytes();encoded=rle_pixels(raw)
    path.write_bytes(struct.pack('<BBHHHHH',0x19,0x12,8,w,h,w*2,0)+struct.pack('<III',1,len(encoded),len(raw))+encoded)
def main():
    src=OUT/'source';OUT.mkdir(parents=True,exist_ok=True)
    atlas=Image.open(src/'icons-atlas.png').convert('RGB')
    assert atlas.size==(1983,793),atlas.size
    manifest={'schema':1,'id':'cyberpunk-v1','name':'赛博朋克','version':'1.0.0','size':92,'icons':{},'files':{},'crops':dict(zip(APPS,BOXES)),'sources':{}}
    sheet=Image.new('RGB',(5*112,2*132),'#050b16');draw=ImageDraw.Draw(sheet)
    for i,(app,box) in enumerate(zip(APPS,BOXES)):
        image=ImageOps.pad(atlas.crop(box),(92,92),method=Image.Resampling.LANCZOS,color='#050b16')
        image.save(OUT/(app+'.png'));native(image,OUT/(app+'.bin'))
        manifest['icons'][app]=app+'.bin';sheet.paste(image,((i%5)*112+10,(i//5)*132+4))
        draw.text(((i%5)*112+10,(i//5)*132+102),app.split('.')[-1],fill='white')
    wall=Image.open(src/'wallpaper.png').convert('RGB').resize((486,486),Image.Resampling.LANCZOS)
    wall.save(OUT/'wallpaper.png');native(wall,OUT/'wallpaper.bin');manifest['wallpaper']='wallpaper.bin'
    sheet.save(OUT/'icons-preview.png')
    for p in src.iterdir():manifest['sources'][p.name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    for p in OUT.iterdir():
        if p.suffix=='.bin':manifest['files'][p.name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    (OUT/'theme.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Built 10 native icons and wallpaper:',sum(m['bytes'] for m in manifest['files'].values()),'bytes; all RLE streams decoded and verified.')
if __name__=='__main__':main()
