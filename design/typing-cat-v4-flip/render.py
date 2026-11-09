"""Preview HH:MM:SS split-flaps and the photo-inspired kitten layout.

UI rendering only. Existing approved illustration is cropped from its sheet.
Nothing in firmware, application resources or the connected device is changed.
"""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ART = ROOT / 'brookesia-apps/flip-clock/assets'
BG = '#08090c'
TEXT = '#dce3f4'
ZH = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 22)
DIGITS = ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf', 82)
POSITIONS = (38, 100, 180, 242, 322, 384)
TOP, WIDTH, HEIGHT, HALF = 140, 58, 100, 49
FLIP_MS = 360
FRAME_MS = 40


def tile(digit):
    im = Image.new('RGB', (WIDTH, HEIGHT), '#111319')
    d = ImageDraw.Draw(im)
    for y in range(HEIGHT):
        v = 19 - round(5*y/HEIGHT)
        d.line((0, y, WIDTH, y), fill=(v, v+2, v+6))
    d.text((WIDTH/2, HEIGHT/2), digit, font=DIGITS, fill=TEXT, anchor='mm')
    return im


TILES = {digit: tile(digit) for digit in '0123456789'}
SCENES = {}
for phase in ('day', 'night'):
    sheet = Image.open(ART / f'cat-{phase}-sheet.png').convert('RGB')
    SCENES[phase] = []
    for i in range(8):
        row, col = divmod(i, 2)
        box = (round(col*sheet.width/2)+2, round(row*sheet.height/4)+2,
               round((col+1)*sheet.width/2)-2, round((row+1)*sheet.height/4)-2)
        SCENES[phase].append(sheet.crop(box).resize((480, 216), Image.Resampling.LANCZOS))


def draw_flap(canvas, x, previous, current, progress):
    old, new = TILES[previous], TILES[current]
    if previous == current or progress >= 1:
        canvas.paste(new, (x, TOP))
    else:
        # New top behind the outgoing upper flap, old bottom underneath.
        canvas.paste(new.crop((0, 0, WIDTH, HALF)), (x, TOP))
        canvas.paste(old.crop((0, HALF+2, WIDTH, HEIGHT)), (x, TOP+HALF+2))
        if progress < .5:
            visible = max(1, round(HALF*math.cos(progress*math.pi)))
            flap = old.crop((0, 0, WIDTH, HALF)).resize((WIDTH, visible), Image.Resampling.LANCZOS)
            canvas.paste(flap, (x, TOP+HALF-visible))
        else:
            visible = max(1, round(HALF*math.sin((progress-.5)*math.pi)))
            flap = new.crop((0, HALF+2, WIDTH, HEIGHT)).resize((WIDTH, visible), Image.Resampling.LANCZOS)
            canvas.paste(flap, (x, TOP+HALF+2))
    ImageDraw.Draw(canvas).rectangle((x, TOP+HALF, x+WIDTH-1, TOP+HALF+1), fill=BG)


def clock_string(seconds):
    return f'{seconds//3600:02d}{seconds//60%60:02d}{seconds%60:02d}'


def render(phase='day', elapsed=0, animate=False):
    im = Image.new('RGB', (480, 480), BG)
    d = ImageDraw.Draw(im)
    # Same hierarchy as the supplied photo: identity / link / battery,
    # then date left and weather right, time above the kitten scene.
    for xy, caption in [((112, 53), '小马时钟'), ((247, 53), 'Wi-Fi'), ((365, 53), '电量86%'),
                        ((147, 105), '11月9日 周一'), ((337, 105), '上海 23°C 多云')]:
        d.text(xy, caption, font=ZH, fill='#c3cedf', anchor='mm')
    base = (12 if phase == 'day' else 20)*3600+29*60+58
    step = int(elapsed//1000) if animate else 0
    current = clock_string(base+step)
    previous = clock_string(base+max(0, step-1))
    progress = min(1, (elapsed%1000)/FLIP_MS) if step else 1
    for i, x in enumerate(POSITIONS):
        draw_flap(im, x, previous[i], current[i], progress)
    d = ImageDraw.Draw(im)
    for x in (169, 311):
        for y in (177, 207):
            d.ellipse((x-3, y-3, x+3, y+3), fill='#abb9d2')
    pose = int(elapsed//180)%8
    if pose == 4 and int(elapsed//1440)%4 != 3:
        pose = 3
    im.paste(SCENES[phase][pose], (0, 242))
    # Keep page indicators at the very bottom, away from the time.
    d = ImageDraw.Draw(im)
    for i in range(3):
        d.ellipse((218+i*18, 465, 225+i*18, 472), fill='#f3e5ce' if i == 2 else '#536078')
    return im


def main():
    for phase in ('day', 'night'):
        render(phase).save(HERE / f'{phase}-layout.png')
    overview = Image.new('RGB', (984, 480), '#22232a')
    overview.paste(render('day'), (0, 0))
    overview.paste(render('night'), (504, 0))
    overview.save(HERE / 'day-night-layout.png')
    palette = overview.quantize(colors=256)
    frames = [render('day', ms, True).quantize(palette=palette, dither=Image.Dither.NONE)
              for ms in range(0, 6000, FRAME_MS)]
    frames[0].save(HERE / 'flip-clock-preview.gif', save_all=True, append_images=frames[1:],
                   duration=FRAME_MS, loop=0, disposal=1, optimize=True)
    # Inspect a genuine minute rollover, rather than six stationary digits.
    strip = Image.new('RGB', (480*5, 118), BG)
    for i, ms in enumerate((1960, 2040, 2160, 2280, 2400)):
        strip.paste(render('day', ms, True).crop((0, 132, 480, 250)), (i*480, 0))
    strip.save(HERE / 'rollover-frames.png')


if __name__ == '__main__':
    main()
