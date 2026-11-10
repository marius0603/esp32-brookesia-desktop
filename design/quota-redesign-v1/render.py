"""Design preview only. Does not generate or install device resources."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
S = 2
W, H = 1240, 790
im = Image.new('RGB', (W*S, H*S), '#eeebe5')
d = ImageDraw.Draw(im)


def font(size, numeric=False, bold=False):
    name = ('segoeuib.ttf' if bold else 'segoeui.ttf') if numeric else 'simhei.ttf'
    return ImageFont.truetype('C:/Windows/Fonts/'+name, round(size*S))


def text(x, y, value, size, color, numeric=False, bold=False, anchor='lt'):
    d.text((round(x*S), round(y*S)), value, font=font(size,numeric,bold), fill=color, anchor=anchor)


def box(rect, fill, radius=0, outline=None, width=1):
    rect = tuple(round(v*S) for v in rect)
    d.rounded_rectangle(rect, radius=round(radius*S), fill=fill, outline=outline, width=round(width*S))


def line(points, color, width=1):
    d.line([(round(x*S),round(y*S)) for x,y in points], fill=color, width=round(width*S))


def circle(x,y,r,color,outline=None,width=1):
    d.ellipse(tuple(round(v*S) for v in (x-r,y-r,x+r,y+r)),fill=color,outline=outline,width=round(width*S))


def screen(ox, oy, dark, phase=0):
    p = ({'root':'#090e17','card':'#151e2c','edge':'#2a3648','ink':'#edf2f8',
          'muted':'#a6b4c7','track':'#0c1420','gold':'#ffd166','mint':'#71ddc9','pill':'#172a28','status':'#91dfbb'}
         if dark else {'root':'#f5eddf','card':'#fffaf2','edge':'#dfd0b7','ink':'#453b31',
          'muted':'#7d6b58','track':'#f0e5d2','gold':'#a86c12','mint':'#197e70','pill':'#e1eddb','status':'#35704e'})
    def b(rect,*args,**kwargs): box((rect[0]+ox,rect[1]+oy,rect[2]+ox,rect[3]+oy),*args,**kwargs)
    def t(x,y,*args,**kwargs):text(ox+x,oy+y,*args,**kwargs)
    b((-7,-7,487,487),'#d9d4cb',46)
    b((-3,-3,483,483),'#b6b2aa',42)
    b((0,0,480,480),p['root'],40)
    b((180,25,300,55),p['pill'],15)
    circle(ox+200,oy+40,3,p['status'])
    t(216,30,'已同步',19,p['status'])
    for index, (title,percent,timer,days,accent) in enumerate((
            ('5小时',73,'02:13:45','',p['gold']),('每周',64,'04:20:11','3天',p['mint']))):
        x,y=26,78+index*194
        b((x,y,x+428,y+178),p['card'],25,p['edge'])
        t(x+22,y+19,title,26,p['ink'])
        number=str(percent)
        t(x+18,y+52,number,80,accent,True,True)
        nw=d.textlength(number,font=font(80,True,True))/S
        t(x+20+nw,y+90,'%',32,accent,True)
        line([(ox+x+214,oy+y+68),(ox+x+214,oy+y+110)],p['edge'])
        circle(ox+x+244,oy+y+86,7,None,p['muted'],1.5)
        line([(ox+x+244,oy+y+81),(ox+x+244,oy+y+86),(ox+x+248,oy+y+89)],p['muted'],1.5)
        if days:t(x+266,y+49,days,18,p['muted'])
        t(x+264,y+73,timer,27,p['ink'],True)
        b((x+18,y+137,x+410,y+169),p['track'],16)
        used=100-percent
        for i in range(20):
            alpha=max(0,min(1,((i+1)*5-used)/5))
            if alpha:
                a=tuple(int(accent[k:k+2],16) for k in (1,3,5))
                bg=tuple(int(p['track'][k:k+2],16) for k in (1,3,5))
                color=tuple(round(c*alpha+b*(1-alpha)) for c,b in zip(a,bg))
                circle(ox+x+18+32+i*18,oy+y+153,2.5,color)
        cx,cy=ox+x+18+15+358*used/100,oy+y+153
        angle=(35,18,2,18)[phase%4]
        d.pieslice(tuple(round(v*S) for v in (cx-14,cy-14,cx+14,cy+14)),angle,360-angle,fill='#ffd166')
        circle(cx+1,cy-7,1.7,'#35281a')


def render(phase=0):
    box((0,0,W,H),'#eeebe5')
    text(76,45,'额度 App / 新版设计',32,'#352f29')
    text(77,96,'大数字 · 低干扰 · 吃豆人轨道',18,'#7a7065')
    text(123,157,'深色模式',21,'#413a31')
    text(683,157,'浅色模式',21,'#413a31')
    screen(100,202,True,phase)
    screen(660,202,False,phase)
    text(100,715,'设计示意 · 百分比与倒计时为演示数据',17,'#7a7065')
    text(100,745,'设计示意，设备实际字体与字号已按实屏调整。',17,'#7a7065')
    return im.resize((W,H),Image.Resampling.LANCZOS)


if __name__ == '__main__':
    render().save(ROOT/'preview.png')
    frames=[render(i).convert('P',palette=Image.Palette.ADAPTIVE,colors=192) for i in range(4)]
    frames[0].save(ROOT/'preview.gif',save_all=True,append_images=frames[1:],duration=200,loop=0,disposal=2)
