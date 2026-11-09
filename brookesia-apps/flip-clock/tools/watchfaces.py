"""Generate original code-drawn clock faces and compose the three-face layout."""
import json,math,struct,sys,shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
APP=Path(__file__).resolve().parents[1];ROOT=APP.parents[1];RES=APP/'src/res'
sys.path.insert(0,str(ROOT/'tools'))
from build_wallpaper_render import rle_pixels
BG='#08090c'
ART_IMAGES={}
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def node(t,id,x,y,w,h,**kw):
 n={'type':t,'id':id,'placement':{'mode':'absolute','x':x,'y':y,'width':w,'height':h},'commonProps':{'scrollable':False,'clickable':False},'style':{'padding':0,'borderWidth':0,'bgOpacity':0}};n.update(kw);return n
def label(id,text,x,y,w,h,size,color='#d4dbea'):
 n=node('label',id,x,y,w,h);n['style'].update(font='${font.zh_CN}',fontSize=size,textColor=color,textAlign='center');n['labelProps']={'text':text};return n
def image(id,src,x,y,w,h):return node('image',id,x,y,w,h,imageProps={'src':'${image.'+src+'}','innerAlign':'contain'})
def group(id,children):
 n=node('container',id,0,0,480,480,children=children);n['bindings']={'commonProps.hidden':'hidden'};return n
def native(name,im):
 ART_IMAGES[name]=im.copy();rgb=im.convert('RGB').tobytes();raw=bytearray()
 for r,g,b in zip(rgb[::3],rgb[1::3],rgb[2::3]):raw+=struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3))
 encoded=rle_pixels(bytes(raw));w,h=im.size
 (RES/'images'/(name+'.bin')).write_bytes(struct.pack('<BBHHHHH',0x19,0x12,8,w,h,w*2,0)+struct.pack('<III',1,len(encoded),len(raw))+encoded)
 return {'id':name,'src':name+'.bin','width':w,'height':h}
def art():
 # Subtle radial brushed-metal face, drawn at double resolution.
 size=680;im=Image.new('RGB',(size,size),BG);px=im.load()
 for y in range(size):
  for x in range(size):
   dx,dy=x-340,y-340;r=math.hypot(dx,dy);a=math.atan2(dy,dx)
   if r<332:
    if r>314:v=int(110+76*math.cos(a-.7)+20*math.cos(a*4))
    else:v=int(20+15*(1-r/320)+13*math.cos(a*4)+2*math.sin(a*240))
    v=max(8,min(225,v));px[x,y]=(v,min(245,int(v*1.08)),min(255,int(v*1.28)))
 d=ImageDraw.Draw(im);d.ellipse((11,11,669,669),outline='#b4bed5',width=2)
 for i in range(60):
  a=i*math.pi/30;inner=282 if i%5==0 else 298
  d.line((340+inner*math.sin(a),340-inner*math.cos(a),340+311*math.sin(a),340-311*math.cos(a)),fill='#edf0fa' if i%5==0 else '#737f9b',width=5 if i%5==0 else 2)
 f=ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf',34)
 for s,x,y in [('12',340,95),('3',585,340),('6',340,585),('9',95,340)]:d.text((x,y),s,font=f,anchor='mm',fill='#e1e6f4')
 d.text((340,219),'XIAOMA',font=ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf',23),anchor='mm',fill='#8e9fbe')
 dial=im.resize((340,340),Image.Resampling.LANCZOS)
 # Original kitten at its laptop; paws are separate native animated objects.
 im=Image.new('RGB',(680,300),'#172235');d=ImageDraw.Draw(im)
 d.rounded_rectangle((2,2,678,298),25,outline='#344665',width=3)
 d.ellipse((542,29,592,79),fill='#e9d59b');d.ellipse((565,20,607,66),fill='#172235')
 for x,y in [(80,48),(153,26),(483,72),(611,100)]:d.ellipse((x,y,x+4,y+4),fill='#cbd3dd')
 d.rectangle((0,240,680,300),fill='#243448');d.line((0,240,680,240),fill='#697385',width=3)
 for x in [15,620]:
  d.polygon([(x,0),(x+46,0),(x+36,125),(x+52,228),(x,228)],fill='#b7746d');d.line((x+22,0,x+14,225),fill='#e8b9a0',width=5)
 # Body, ears and head.
 d.ellipse((252,122,431,266),fill='#db9b55',outline='#77472e',width=4)
 d.polygon([(247,96),(246,19),(307,60),(380,54),(443,17),(435,110)],fill='#e6a866',outline='#77472e',width=5)
 d.polygon([(259,75),(259,35),(294,61)],fill='#dfb0a1');d.polygon([(399,61),(432,33),(427,85)],fill='#dfb0a1')
 d.ellipse((238,53,445,223),fill='#efba78',outline='#77472e',width=4)
 d.ellipse((262,133,425,223),fill='#f7dfb5')
 # Eyes are native overlays so blinking needs no replacement scene bitmap.
 d.polygon([(334,148),(349,148),(341,158)],fill='#b56e6b');d.arc((325,150,342,173),0,100,fill='#775141',width=3);d.arc((341,150,358,173),80,180,fill='#775141',width=3)
 for points in [[(322,61),(331,87)],[(341,57),(343,85)],[(361,61),(354,87)]]:d.line(points,fill='#bb733a',width=10)
 for x,sgn in [(266,-1),(417,1)]:
  for dy in [-8,8]:d.line((x,161+dy,x+sgn*35,157+dy*2),fill='#ac805c',width=2)
 # Laptop keyboard and lid rim, plus a small mug.
 d.rounded_rectangle((226,223,460,280),9,fill='#758ab4',outline='#acb9cf',width=3)
 for row in range(3):
  for col in range(10):d.rounded_rectangle((238+col*21,232+row*12,254+col*21,239+row*12),2,fill='#263855')
 d.rounded_rectangle((69,220,113,259),8,fill='#e3ccb0');d.arc((101,223,131,251),-90,90,fill='#e3ccb0',width=6)
 return native('metal_dial',dial),native('cat_scene',im.resize((340,150),Image.Resampling.LANCZOS))
def previews():
 f=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
 for name in ['metal','cat']:
  im=Image.new('RGB',(480,480),BG);d=ImageDraw.Draw(im)
  d.text((152,62),'Wi-Fi 已连接',font=f(16),fill='#8196b5',anchor='mm');d.text((341,62),'电量 86%',font=f(16),fill='#8196b5',anchor='mm')
  if name=='metal':
   im.paste(ART_IMAGES['metal_dial'],(70,70));d=ImageDraw.Draw(im)
   for angle,length,width,col,tail in [(15,93,7,'#d7e1f4',10),(180,133,4,'#ecf3ff',10),(240,145,2,'#eb725f',20)]:
    a=angle*math.pi/180;d.line((240-tail*math.sin(a),240+tail*math.cos(a),240+length*math.sin(a),240-length*math.cos(a)),fill=col,width=width)
   d.ellipse((235,235,245,245),fill='#dbe4f5');dy=428;wy=457
  else:
   d.text((240,207),'12:30',font=ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf',82),fill='#e5e9f8',anchor='mm')
   im.paste(ART_IMAGES['cat_scene'],(70,267));d=ImageDraw.Draw(im)
   for x in [210,258]:d.rounded_rectangle((x,323,x+14,341),7,fill='#342d2f');d.ellipse((x+4,326,x+8,330),fill='white')
   for x,y in [(203,371),(247,376)]:
    d.rounded_rectangle((x,y,x+32,y+18),9,fill='#f4d9ac',outline='#ae7748')
    for dx in [10,18]:d.line((x+dx,y+8,x+dx,y+12),fill='#b88c5c')
   for i in range(3):d.ellipse((221+i*16,128,227+i*16,134),fill='#d7e3f9' if i==2 else '#536078')
   dy=104;wy=438
  d.text((240,dy),'11月9日  周一',font=f(19),fill='#d4dbea',anchor='mm');d.text((240,wy),'上海  23°C  多云',font=f(20),fill='#c3cedf',anchor='mm')
  im.save(APP/('watchface-'+name+'-preview.png'))

def augment():
 layout=json.loads((RES/'screens/main.json').read_text());old=layout['children'];flip=next((n for n in old if n['id']=='flip'),None)
 if flip is None:flip=group('flip',old)
 dial,cat=art();analog=[image('dial','metal_dial',70,70,340,340)]
 for name,length,width,color in [('hour',93,7,'#d7e1f4'),('minute',133,4,'#ecf3ff'),('second',145,2,'#eb725f')]:
  n=node('line',name,70,70,340,340);n['style'].update(lineWidth=width,lineColor=color);n['lineProps']={'points':[{'x':170,'y':190 if name=='second' else 180},{'x':170,'y':170-length}]};n['bindings']={'lineProps.points':'points'};analog.append(n)
 hub=node('container','hub',235,235,10,10);hub['style'].update(bgColor='#dbe4f5',bgOpacity=255,radius=5);analog.append(hub)
 companion=[label('time','--:--',50,152,380,105,82,'#e5e9f8'),image('scene','cat_scene',70,267,340,150)]
 for id,x in [('leftEye',210),('rightEye',258)]:
  n=node('container',id,x,323,14,18);n['style'].update(bgColor='#342d2f',bgOpacity=255,radius=7);n['bindings']={'placement.y':'y','placement.height':'height'}
  glint=node('container','glint',4,3,4,4);glint['style'].update(bgColor='#ffffff',bgOpacity=255,radius=2);glint['bindings']={'commonProps.hidden':'hidden'};n['children']=[glint];companion.append(n)
 for id,x in [('leftPaw',203),('rightPaw',247)]:
  n=node('container',id,x,373,32,18);n['style'].update(bgColor='#f4d9ac',bgOpacity=255,borderColor='#ae7748',borderWidth=1,radius=9);n['bindings']={'placement.y':'y'}
  n['children']=[]
  for i in range(2):
   toe=node('line','toe'+str(i),10+i*8,8,2,5);toe['style'].update(lineColor='#b88c5c',lineWidth=1);toe['lineProps']={'points':[{'x':0,'y':0},{'x':0,'y':4}]};n['children'].append(toe)
  companion.append(n)
 shared=[label('network','Wi-Fi --',76,50,180,24,16,'#8196b5'),label('battery','电量 --',279,50,125,24,16,'#8196b5'),label('date','--月--日',80,91,320,27,19)]
 # Analog date sits beneath the dial; companion date stays above its digits.
 shared[-1]['bindings']={'placement.y':'y'}
 shared+=[label('weather','天气待更新',75,424,330,29,20,'#c3cedf'),label('weatherAge','',105,455,270,18,12,'#8390a6')]
 for i in range(3):
  n=node('container','page'+str(i),221+i*16,128,6,6);n['style'].update(bgColor='#56647e',bgOpacity=255,radius=3);n['bindings']={'style.bgColor':'color'};shared.append(n)
 for n in shared:
  if n['id']=='weather':n['bindings']={'placement.y':'y'}
  if n['id']=='weatherAge' or n['id'].startswith('page'):n.setdefault('bindings',{})['commonProps.hidden']='hidden'
 status=group('status',shared)
 hit=node('container','swipe',0,35,480,410);hit['commonProps'].update(clickable=True,pressLock=True);hit['events']=[{'type':'pressed','action':'facePress'},{'type':'released','action':'faceRelease'},{'type':'pressLost','action':'faceCancel'}]
 layout['children']=[flip,group('analog',analog),group('companion',companion),status,hit];write(RES/'screens/main.json',layout)
 idx=json.loads((RES/'images/index.json').read_text());idx['images']=[i for i in idx['images'] if i['id'] not in ['metal_dial','cat_scene']]+[dial,cat]
 for i in idx['images']:
  if i['id']=='launcher_icon':
   src=ROOT/'themes/cartoon-q-v1/launcher-optimized/local.flipclock.bin';shutil.copyfile(src,RES/'images/launcher_icon.bin');i['src']='launcher_icon.bin'
 write(RES/'images/index.json',idx)
 manifest=json.loads((APP/'src/manifest.json').read_text());manifest['package']['version']='0.2.0'
 for service,version in [('Wifi','0.8.2'),('Http','0.8.2'),('DeviceModes','0.1.0')]:
  if not any(s['name']==service for s in manifest['services']):manifest['services'].append({'name':service,'version':version})
 write(APP/'src/manifest.json',manifest)
 previews()
 write(APP/'package.json',{'name':'local-flip-clock','version':'0.2.0','private':True})
 root=json.loads((RES/'root.json').read_text());root['version']='0.2.0';write(RES/'root.json',root)
if __name__=='__main__':augment()
