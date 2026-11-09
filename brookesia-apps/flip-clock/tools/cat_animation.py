"""Convert the approved imagegen sheets into native RGB565 clock resources.

Only package/crop/resize the authored raster art. Never synthesize replacement
cat shapes. Runtime uses one image view, not sixteen permanently pinned frames.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_wallpaper_render import rle_pixels


def export():
    images = APP / 'src/res/images'
    index_path = images / 'index.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    index['images'] = [item for item in index['images'] if not item['id'].startswith('cat_')]
    for old in images.glob('cat_*.bin'):
        old.unlink()
    info = {'frame_size': [216,216], 'scene_size':[480,216], 'motion_crop':[152,0,216,216], 'frame_ms':180, 'frames_per_phase':8, 'sources':{}}
    first = {}
    def encode(name,frame):
        rgb=frame.tobytes();raw=bytearray()
        for r,g,b in zip(rgb[::3],rgb[1::3],rgb[2::3]):
            raw+=struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3))
        encoded=rle_pixels(bytes(raw));w,h=frame.size
        data=struct.pack('<BBHHHHH',0x19,0x12,8,w,h,w*2,0)+struct.pack('<III',1,len(encoded),len(raw))+encoded
        (images/(name+'.bin')).write_bytes(data)
        index['images'].append({'id':name,'src':name+'.bin','width':w,'height':h})
    for phase in ('day', 'night'):
        source = APP / f'assets/cat-{phase}-sheet.png'
        sheet = Image.open(source).convert('RGB')
        info['sources'][phase] = {'file': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        for number in range(8):
            row, col = divmod(number, 2)
            box = (round(col * sheet.width / 2) + 2, round(row * sheet.height / 4) + 2,
                   round((col + 1) * sheet.width / 2) - 2, round((row + 1) * sheet.height / 4) - 2)
            frame = sheet.crop(box).resize((480, 216), Image.Resampling.LANCZOS)
            if number == 0:
                first[phase] = frame
                encode('cat_background_'+phase,frame)
            frame=frame.crop((152,0,368,216))
            name = f'cat_{phase}_{number}'
            encode(name,frame)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (APP / 'assets/animation.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    from status_icons import wifi, battery, weather
    from watchfaces import ART_IMAGES
    font = lambda size: ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', size)
    for phase, frame in first.items():
        preview = Image.new('RGB', (480, 480), '#08090c')
        d = ImageDraw.Draw(preview)
        for icon, xy, size in [(wifi(), (218,12), (44,33)), (battery(86), (393,12), (48,36)),
                               (weather(2,phase=='day'), (312,78), (40,30))]:
            icon=icon.resize(size,Image.Resampling.LANCZOS);preview.paste(icon,xy,icon)
        for xy, caption, size in [((134,96), '11月9日 周一',28), ((277,96),'上海',28), ((399,96),'23°C',28)]:
            d.text(xy, caption, font=font(size), fill='#bfcbdc', anchor='mm')
        value='122958' if phase=='day' else '202958'
        for digit,x in zip(value,[38,100,180,242,322,384]):
            preview.paste(ART_IMAGES['clock_top_'+digit],(x,140))
            preview.paste(ART_IMAGES['clock_bottom_'+digit],(x,191))
        for x,y in [(166,174),(166,204),(308,174),(308,204)]:d.ellipse((x,y,x+6,y+6),fill='#abb9d2')
        for i in range(3):
            d.ellipse((218+i*18,465,225+i*18,472), fill='#d7e3f9' if i == 2 else '#536078')
        preview.paste(frame, (0,242))
        preview.save(APP / f'watchface-cat-{phase}-preview.png')
    first['night'].save(APP / 'assets/cat-scene-preview.png')


if __name__ == '__main__':
    export()
