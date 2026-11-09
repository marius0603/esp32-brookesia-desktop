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
    info = {'frame_size': [340, 150], 'frame_ms': 180, 'frames_per_phase': 8, 'sources': {}}
    first = {}
    for phase in ('day', 'night'):
        source = APP / f'assets/cat-{phase}-sheet.png'
        sheet = Image.open(source).convert('RGB')
        info['sources'][phase] = {'file': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        for number in range(8):
            row, col = divmod(number, 2)
            box = (round(col * sheet.width / 2) + 2, round(row * sheet.height / 4) + 2,
                   round((col + 1) * sheet.width / 2) - 2, round((row + 1) * sheet.height / 4) - 2)
            frame = sheet.crop(box).resize((340, 150), Image.Resampling.LANCZOS)
            if number == 0:
                first[phase] = frame
            rgb = frame.tobytes()
            raw = bytearray()
            for r, g, b in zip(rgb[::3], rgb[1::3], rgb[2::3]):
                raw += struct.pack('<H', ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
            encoded = rle_pixels(bytes(raw))
            name = f'cat_{phase}_{number}'
            data = struct.pack('<BBHHHHH', 0x19, 0x12, 8, 340, 150, 680, 0)
            data += struct.pack('<III', 1, len(encoded), len(raw)) + encoded
            (images / (name + '.bin')).write_bytes(data)
            index['images'].append({'id': name, 'src': name + '.bin', 'width': 340, 'height': 150})
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (APP / 'assets/animation.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    font = lambda size: ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', size)
    for phase, frame in first.items():
        preview = Image.new('RGB', (480, 480), '#08090c')
        d = ImageDraw.Draw(preview)
        for xy, caption, size in [((152, 62), 'Wi-Fi 已连接', 16), ((341, 62), '电量 86%', 16),
                                   ((155, 104), '11月9日 周一', 16), ((326, 104), '上海 23°C 多云', 16)]:
            d.text(xy, caption, font=font(size), fill='#bfcbdc', anchor='mm')
        d.text((240, 207), '12:30' if phase == 'day' else '20:30',
               font=ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf', 82), fill='#e5e9f8', anchor='mm')
        for i in range(3):
            d.ellipse((221+i*16, 128, 227+i*16, 134), fill='#d7e3f9' if i == 2 else '#536078')
        preview.paste(frame, (70, 267))
        preview.save(APP / f'watchface-cat-{phase}-preview.png')
    first['night'].save(APP / 'assets/cat-scene-preview.png')


if __name__ == '__main__':
    export()
