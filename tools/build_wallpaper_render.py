"""Convert existing wallpaper artwork to a native, presized LVGL RGB565 asset."""
import argparse
from array import array
import hashlib
import json
from pathlib import Path
import struct
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RENDER_NAME = 'wallpaper-486-rgb565.bin'


def rle_pixels(raw):
    pixels = [raw[i:i+2] for i in range(0, len(raw), 2)]
    encoded = bytearray()
    i = 0
    while i < len(pixels):
        repeat = 1
        while repeat < 127 and i+repeat < len(pixels) and pixels[i+repeat] == pixels[i]:
            repeat += 1
        if repeat >= 3:
            encoded.append(repeat)
            encoded.extend(pixels[i])
            i += repeat
        else:
            start = i
            i += repeat
            while i < len(pixels) and i-start < 127:
                if i+2 < len(pixels) and pixels[i] == pixels[i+1] == pixels[i+2]:
                    break
                i += 1
            encoded.append(0x80 | (i-start))
            encoded.extend(raw[start*2:i*2])
    # Independent decode checks that the exported stream preserves every pixel.
    decoded = bytearray()
    pos = 0
    while pos < len(encoded):
        control = encoded[pos]
        pos += 1
        count = control & 0x7f
        size = count*2 if control & 0x80 else 2
        block = encoded[pos:pos+size]
        decoded.extend(block if control & 0x80 else block*count)
        pos += size
    assert decoded == raw
    return encoded


def export_wallpaper(source, destination):
    with Image.open(source) as image:
        rgb = image.convert('RGB').resize((486, 486), Image.Resampling.LANCZOS)
        pixels = array('H', (((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                             for r, g, b in rgb.getdata()))
    if sys.byteorder != 'little':
        pixels.byteswap()
    # LVGL v9: magic, RGB565, flags, width, height, stride, reserved.
    raw = pixels.tobytes()
    encoded = rle_pixels(raw)
    header = struct.pack('<BBHHHHH', 0x19, 0x12, 8, 486, 486, 972, 0)
    compression = struct.pack('<III', 1, len(encoded), len(raw))
    destination.write_bytes(header + compression + encoded)
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--theme', type=Path, default=ROOT/'themes/cream-handdrawn-v1')
    args = parser.parse_args()
    manifest_path = args.theme/'theme.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    target = export_wallpaper(args.theme/manifest['wallpaper'], args.theme/RENDER_NAME)
    manifest['wallpaper_render'] = RENDER_NAME
    manifest['files'][RENDER_NAME] = {'bytes': target.stat().st_size,
                                     'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print('Native wallpaper:', target, target.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
