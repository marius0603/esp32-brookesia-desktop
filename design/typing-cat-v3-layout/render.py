"""Review-only layout render using the approved artwork, no device changes."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ART = ROOT / 'brookesia-apps/flip-clock/assets'
FONT = 'C:/Windows/Fonts/msyh.ttc'


def render(phase, index=0):
    im = Image.new('RGB', (480, 480), '#08090c')
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(FONT, 22)
    for xy, text in [((155, 59), 'Wi-Fi 已连接'), ((339, 59), '电量 86%'),
                     ((151, 106), '11月9日 周一'), ((335, 106), '上海 23°C 多云')]:
        d.text(xy, text, font=font, anchor='mm', fill='#c3cedf')
    d.text((240, 196), '12:30' if phase == 'day' else '20:30',
           font=ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf', 82), anchor='mm', fill='#e5e9f8')
    sheet = Image.open(ART / f'cat-{phase}-sheet.png').convert('RGB')
    row, col = divmod(index, 2)
    box = (round(col*sheet.width/2)+2, round(row*sheet.height/4)+2,
           round((col+1)*sheet.width/2)-2, round((row+1)*sheet.height/4)-2)
    scene = sheet.crop(box).resize((480, 216), Image.Resampling.LANCZOS)
    im.paste(scene, (0, 242))
    d = ImageDraw.Draw(im)
    for i in range(3):
        d.ellipse((218+i*18, 465, 225+i*18, 472), fill='#f3e5ce' if i == 2 else '#536078')
    return im


if __name__ == '__main__':
    for phase in ('day', 'night'):
        render(phase).save(HERE / f'{phase}-layout.png')
    overview = Image.new('RGB', (984, 480), '#22232a')
    overview.paste(render('day'), (0, 0))
    overview.paste(render('night'), (504, 0))
    overview.save(HERE / 'day-night-layout.png')
