"""Deterministic 480x480 navigation concept. Preview only; no production resources."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
OUT=Path(__file__).resolve().parent
S=3
def font(n,bold=False):return ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc',round(n*S))
def panel(dark):
 p={'bg':'#090f19','surface':'#162431','line':'#344956','ink':'#edf5fa','muted':'#9cafbb','accent':'#72e1c4','pill':'#183a35'} if dark else {'bg':'#f7f0e3','surface':'#fffaf1','line':'#dfd1b8','ink':'#453e35','muted':'#867966','accent':'#1b8f7c','pill':'#dfeddf'}
 im=Image.new('RGB',(480*S,480*S),p['bg']);d=ImageDraw.Draw(im)
 def line(points,fill,w=2):d.line([(int(x*S),int(y*S)) for x,y in points],fill=fill,width=round(w*S),joint='curve')
 def text(x,y,t,n,fill=None,b=False,anchor='lt'):d.text((x*S,y*S),t,font=font(n,b),fill=fill or p['ink'],anchor=anchor)
 def box(x,y,w,h,fill,r=16,outline=None):d.rounded_rectangle((x*S,y*S,(x+w)*S,(y+h)*S),radius=r*S,fill=fill,outline=outline,width=S)
 def speaker(x,y,c,muted=False):
  d.polygon([(x*S,(y+8)*S),((x+6)*S,(y+8)*S),((x+14)*S,(y+2)*S),((x+14)*S,(y+26)*S),((x+6)*S,(y+20)*S),(x*S,(y+20)*S)],fill=c)
  for r in (7,13):d.arc(((x+8)*S,(y+14-r)*S,(x+8+2*r)*S,(y+14+r)*S),-48,48,fill=c,width=2*S)
 # Three independent fixed status groups; no title or black status-bar plate.
 line([(62,30),(62,56),(73,46),(53,35),(73,46),(62,56)],p['accent'],2)
 d.ellipse((82*S,39*S,88*S,45*S),fill=p['accent'])
 speaker(190,29,p['muted']);text(229,28,'70%',22,b=True)
 d.rounded_rectangle((369*S,33*S,399*S,49*S),radius=4*S,outline=p['muted'],width=2*S)
 box(373,37,21,8,p['accent'],2);box(401,38,3,6,p['muted'],1)
 # A single oversized bent direction arrow is the hero, not a map texture.
 line([(176,224),(176,151),(302,151)],p['accent'],30)
 d.polygon([(292*S,108*S),(340*S,151*S),(292*S,194*S)],fill=p['accent'])
 # Thick stems have rounded caps, preserving a clean silhouette at 480px.
 d.ellipse((161*S,209*S,191*S,239*S),fill=p['accent'])
 text(230,247,'200',72,b=True,anchor='mt');text(345,285,'米',26)
 box(94,337,292,39,p['surface'],15)
 text(240,342,'右转进入示例路',23,anchor='mt')
 # Remaining distance / time are icon-labelled and secondary.
 line([(100,397),(100,385),(109,389),(100,392)],p['muted'],2);text(119,381,'2.4 km',20,fill=p['muted'])
 d.ellipse((277*S,384*S,294*S,401*S),outline=p['muted'],width=2*S);line([(286,387),(286,393),(291,395)],p['muted'],2);text(304,381,'8 分钟',20,fill=p['muted'])
 box(52,419,166,38,p['pill'],15);speaker(71,424,p['accent']);text(116,423,'播报开启',20,fill=p['accent'])
 for x,plus in [(262,False),(340,True)]:
  box(x,419,64,38,p['surface'],14,outline=p['line']);line([(x+22,438),(x+42,438)],p['ink'],3)
  if plus:line([(x+32,428),(x+32,448)],p['ink'],3)
 return im.resize((480,480),Image.Resampling.LANCZOS)
def main():
 canvas=Image.new('RGB',(1240,750),'#e8e6e1');d=ImageDraw.Draw(canvas)
 def t(x,y,s,size,color='#292b2d',bold=False):d.text((x,y),s,font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc',size),fill=color)
 t(64,30,'小马导航 / 图形优先',32,bold=True);t(64,78,'480 × 480 · 示例数据 · 界面设计预览，尚未实装',19,'#727373')
 for x,dark,label in [(80,True,'深色模式'),(680,False,'浅色模式')]:
  screen=panel(dark);mask=Image.new('L',(480,480));ImageDraw.Draw(mask).rounded_rectangle((0,0,479,479),radius=48,fill=255)
  d.rounded_rectangle((x-8,132,x+488,628),radius=56,fill='#c7c8c6');canvas.paste(screen,(x,140),mask)
  t(x,647,label,22,bold=True)
 t(64,705,'大转向箭头   /   顶部音量百分比   /   语音开关与音量调节   /   随系统切换深浅色',19,'#666b69')
 canvas.save(OUT/'navigation-preview.png')
 for dark,name in [(True,'dark'),(False,'light')]:panel(dark).save(OUT/('navigation-'+name+'.png'))
 print(OUT/'navigation-preview.png')
if __name__=='__main__':main()
