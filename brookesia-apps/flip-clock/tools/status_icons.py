"""Small native UI symbols, supersampled for clean 480px mockups."""
from PIL import Image, ImageDraw
import math

INK = '#c3cedf'
SCALE = 4


def canvas():
    im = Image.new('RGBA', (64*SCALE, 48*SCALE))
    return im, ImageDraw.Draw(im)


def box(values):
    return tuple(round(v*SCALE) for v in values)


def stroke(d, points, fill=INK, width=2):
    d.line(box(points), fill=fill, width=round(width*SCALE))
    radius = width/2
    for x, y in (points[:2], points[-2:]):
        d.ellipse(box((x-radius, y-radius, x+radius, y+radius)), fill=fill)


def wifi(connected=True):
    im, d = canvas()
    for radius in (23, 16, 9):
        d.arc(box((32-radius, 37-radius, 32+radius, 37+radius)), 222, 318,
              fill=INK, width=3*SCALE)
    d.ellipse(box((29.5, 34.5, 34.5, 39.5)), fill=INK)
    if not connected:
        stroke(d, (18, 11, 46, 41), '#f09c8c', 3)
    return im


def battery(level=86, charging=False):
    im, d = canvas()
    level = max(0, min(100, level))
    d.rounded_rectangle(box((8, 12, 54, 36)), radius=4*SCALE, outline=INK, width=2*SCALE)
    d.rounded_rectangle(box((56, 19, 60, 29)), radius=1*SCALE, fill=INK)
    if level:
        d.rounded_rectangle(box((12, 16, 12+38*level/100, 32)), radius=2*SCALE,
                            fill='#ed8d7d' if level <= 20 else INK)
    if charging:
        d.polygon(box((34, 13, 24, 26, 31, 26, 29, 36, 41, 22, 34, 22)), fill='#f4c76d')
    return im


def sun(d, x=29, y=21, radius=10):
    for i in range(8):
        angle = i*math.pi/4
        stroke(d, (x+(radius+3)*math.cos(angle), y+(radius+3)*math.sin(angle),
                   x+(radius+7)*math.cos(angle), y+(radius+7)*math.sin(angle)), '#f2c56e', 2)
    d.ellipse(box((x-radius, y-radius, x+radius, y+radius)), fill='#f2c56e')


def moon(im, x=25, y=20):
    # Alpha cutout, not an opaque patch matching one specific background.
    layer, d = canvas()
    d.ellipse(box((x-13, y-13, x+13, y+13)), fill='#eeddb2')
    d.ellipse(box((x-4, y-17, x+17, y+5)), fill=(0, 0, 0, 0))
    im.alpha_composite(layer)


def cloud(d, shade='#c6d5e8', dy=0):
    for bounds in [(18, 23, 40, 40), (25, 15, 47, 39), (38, 22, 57, 40)]:
        d.ellipse(box((bounds[0], bounds[1]+dy, bounds[2], bounds[3]+dy)), fill=shade)
    d.rounded_rectangle(box((22, 29+dy, 52, 40+dy)), radius=5*SCALE, fill=shade)


def weather(code=2, day=True):
    im, d = canvas()
    if code == 0:
        if day:
            sun(d, 32, 24, 11)
        else:
            moon(im, 32, 25)
        return im
    if code in (1, 2):
        if day:
            sun(d, 24, 17, 9)
        else:
            moon(im, 24, 18)
        cloud(d)
    elif code == 3:
        cloud(d, '#a6b8d0')
    elif code in (45, 48):
        cloud(d, '#a6b8d0', -7)
        for y, x1, x2 in ((34, 15, 50), (40, 21, 57), (46, 17, 46)):
            stroke(d, (x1, y, x2, y), '#c6d5e8', 2)
    elif code in (95, 96, 97, 99):
        cloud(d, '#a6b8d0', -9)
        d.polygon(box((35, 27, 27, 39, 34, 39, 31, 48, 44, 33, 36, 33)), fill='#f2c56e')
    elif code in (71, 73, 75, 77, 85, 86):
        cloud(d, dy=-9)
        for x in (24, 38, 51):
            for a in (0, math.pi/3, math.pi*2/3):
                stroke(d, (x-3*math.cos(a), 41-3*math.sin(a), x+3*math.cos(a), 41+3*math.sin(a)), '#bbdcf7', 1.3)
    elif code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        cloud(d, dy=-9)
        for x in (25, 38, 51):
            stroke(d, (x, 36, x-3, 44), '#79b8e8', 2)
    else:
        d.ellipse(box((19, 8, 47, 36)), outline=INK, width=2*SCALE)
        stroke(d, (33, 15, 33, 24), INK, 2)
        d.ellipse(box((32, 28, 34, 30)), fill=INK)
    return im


def paste(canvas_image, icon, xy, size):
    canvas_image.alpha_composite(icon.resize(size, Image.Resampling.LANCZOS), xy)
