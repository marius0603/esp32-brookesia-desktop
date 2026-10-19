"""Draw a deterministic rain-on-glass texture and a small animated droplet."""
import math
from pathlib import Path
import random
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[1] / 'src/res/images'
OUT.mkdir(parents=True, exist_ok=True)
random.seed(216)
size = 320
base = Image.new('RGB', (size, size))
for y in range(size):
    for x in range(size):
        glow = math.exp(-((x-270)**2+(y-55)**2)/18000)
        base.putpixel((x,y), (int(7+12*glow), int(19+34*glow), int(32+43*glow)))
bokeh = Image.new('RGBA', base.size)
d = ImageDraw.Draw(bokeh)
for _ in range(30):
    x, y = random.randrange(-20,340), random.randrange(210,355)
    r = random.randrange(3,18)
    color = random.choice([(69,145,184,170),(213,171,98,160),(78,158,167,130)])
    d.ellipse((x-r,y-r,x+r,y+r),fill=color)
bokeh = bokeh.filter(ImageFilter.GaussianBlur(12))
glass = Image.alpha_composite(base.convert('RGBA'), bokeh)
source = glass.copy()
water = Image.new('RGBA', glass.size)
d = ImageDraw.Draw(water)
for _ in range(100):
    x,y = random.randrange(6,314),random.randrange(8,316)
    r = random.choice([1.6,2,2.5,3,4.5,6,8])
    ry = r*random.uniform(1,1.8)
    # Convex water lenses refract a small shifted area of the blurred scene.
    for py in range(max(0,int(y-ry)),min(size,int(y+ry+1))):
        for px in range(max(0,int(x-r)),min(size,int(x+r+1))):
            nx,ny=(px-x)/r,(py-y)/ry
            q=nx*nx+ny*ny
            if q<0.92:
                sx=max(0,min(size-1,int(x+nx*r*.65+3)))
                sy=max(0,min(size-1,int(y+ny*ry*.65+5)))
                c=source.getpixel((sx,sy))
                glass.putpixel((px,py),(min(255,int(c[0]*1.2+4)),min(255,int(c[1]*1.2+7)),min(255,int(c[2]*1.15+9)),255))
    box=(x-r,y-ry,x+r,y+ry)
    d.arc(box,35,195,fill=(0,5,12,150),width=1)
    d.arc(box,210,300,fill=(199,232,246,125),width=1)
    d.ellipse((x-r*.5,y-ry*.65,x-r*.1+1,y-ry*.3),fill=(214,242,255,95))
    if r>4 and random.random()<.6:
        d.line((x,y-ry-22,x,y-ry),fill=(163,205,226,24),width=1)
Image.alpha_composite(glass,water).save(OUT/'rain_glass.png')

drop=Image.new('RGBA',(20,48));d=ImageDraw.Draw(drop)
d.line((10,0,10,31),fill=(202,234,248,32),width=2)
d.ellipse((4,26,16,45),fill=(45,83,108,105),outline=(174,215,238,105),width=1)
d.arc((6,28,14,42),190,275,fill=(233,249,255,205),width=2)
d.arc((5,28,15,44),10,105,fill=(0,9,21,150),width=2)
drop.save(OUT/'sliding_drop.png')
print(OUT)
