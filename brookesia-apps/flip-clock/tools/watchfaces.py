"""Generate original code-drawn clock faces and compose the three-face layout."""
import json,math,struct,sys,shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
APP=Path(__file__).resolve().parents[1];ROOT=APP.parents[1];RES=APP/'src/res'
sys.path.insert(0,str(ROOT/'tools'))
from build_wallpaper_render import rle_pixels
from status_icons import wifi,battery,weather,box,stroke,INK
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

def png(name,im,size):
 im.resize(size,Image.Resampling.LANCZOS).save(RES/'images'/(name+'.png'))
 return {'id':name,'src':name+'.png','width':size[0],'height':size[1]}

def modern_widgets():
 resources=[];companion=[image('scene','cat_background_night',0,242,480,216),image('motion','cat_night_0',152,242,216,216)]
 font=ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf',82)
 for digit in '0123456789-':
  im=Image.new('RGB',(58,100));d=ImageDraw.Draw(im)
  for y in range(100):
   v=19-round(5*y/100);d.line((0,y,58,y),fill=(v,v+2,v+6))
  d.text((29,50),digit,font=font,fill='#dce3f4',anchor='mm')
  for part,bounds in [('top',(0,0,58,49)),('bottom',(0,51,58,100))]:resources.append(native('clock_'+part+'_'+digit,im.crop(bounds)))
 for i,x in enumerate([38,100,180,242,322,384]):
  children=[]
  for part,y in [('top',0),('bottom',51),('flap',0),('incoming',51)]:
   item=image(part,'clock_'+('top' if part=='flap' else 'bottom' if part=='incoming' else part)+'_-',0,y,58,49)
   item['imageProps']['innerAlign']='stretch'
   if part in ('flap','incoming'):
    item['style']['opacity']=0;item['commonProps']['hidden']=True;item['bindings']={'placement.y':'y','placement.height':'height','style.opacity':'opacity','commonProps.hidden':'hidden'}
   children.append(item)
  companion.append(node('container','d'+str(i),x,140,58,100,children=children))
 for i,(x,y) in enumerate([(166,174),(166,204),(308,174),(308,204)]):
  dot=node('container','colon'+str(i),x,y,7,7);dot['style'].update(bgColor='#abb9d2',bgOpacity=255,radius=4);companion.append(dot)
 resources+=[png('icon_wifi_on',wifi(),(44,33)),png('icon_wifi_off',wifi(False),(44,33))]
 for level in range(11):
  for charge in [False,True]:resources.append(png('icon_battery_'+('charge_' if charge else '')+str(level),battery(level*10,charge),(48,36)))
 for kind in ['unknown','usb']:
  im=battery(0);d=ImageDraw.Draw(im)
  if kind=='unknown':stroke(d,(26,24,39,24),INK,2)
  else:
   d.rounded_rectangle(box((25,19,39,28)),radius=2*4,outline=INK,width=2*4)
   for x in [28,36]:stroke(d,(x,14,x,19),INK,2)
   stroke(d,(32,28,32,32),INK,2)
  resources.append(png('icon_battery_'+kind,im,(48,36)))
 for name,code,day in [('clear_day',0,True),('clear_night',0,False),('partly_day',2,True),('partly_night',2,False),('clouds',3,True),('fog',45,True),('rain',61,True),('snow',71,True),('thunder',95,True),('unknown',-1,True)]:
  resources.append(png('icon_weather_'+name,weather(code,day),(40,30)))
 date=label('date','--月--日',32,77,205,38,28,'#c3cedf')
 date['bindings']={'placement.y':'y','placement.x':'x','placement.width':'width','style.fontSize':'fontSize'}
 city=label('city','上海',248,0,58,38,28,'#c3cedf')
 temperature=label('temperature','--°C',358,0,82,38,28,'#c3cedf')
 symbol=image('symbol','icon_weather_unknown',312,1,40,30)
 for item in [city,temperature,symbol]:
  item['bindings']={'placement.x':'x'}
  if item['type']=='label':item['bindings'].update({'placement.width':'width','style.fontSize':'fontSize'})
 weather_row=node('container','weather',0,77,480,38,children=[city,symbol,temperature]);weather_row['bindings']={'placement.y':'y'}
 shared=[image('network','icon_wifi_off',218,12,44,33),image('battery','icon_battery_unknown',393,12,48,36),date,weather_row]
 age=label('weatherAge','',105,116,270,18,12,'#8390a6');age['bindings']={'commonProps.hidden':'hidden'};shared.append(age)
 dots=[]
 for i in range(3):
  dot=node('container','page'+str(i),218+i*18,465,8,8);dot['style'].update(bgColor='#536078',bgOpacity=255,radius=4);dot['bindings']={'style.bgColor':'color'};dots.append(dot)
 return companion,group('status',shared),group('pager',dots),resources
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
 return native('metal_dial',dial)

def previews():
 f=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
 for name in ['metal']:
  im=Image.new('RGB',(480,480),BG);d=ImageDraw.Draw(im)
  d.text((152,62),'Wi-Fi 已连接',font=f(16),fill='#8196b5',anchor='mm');d.text((341,62),'电量 86%',font=f(16),fill='#8196b5',anchor='mm')
  if name=='metal':
   im.paste(ART_IMAGES['metal_dial'],(70,70));d=ImageDraw.Draw(im)
   for angle,length,width,col,tail in [(15,93,7,'#d7e1f4',10),(180,133,4,'#ecf3ff',10),(240,145,2,'#eb725f',20)]:
    a=angle*math.pi/180;d.line((240-tail*math.sin(a),240+tail*math.cos(a),240+length*math.sin(a),240-length*math.cos(a)),fill=col,width=width)
   d.ellipse((235,235,245,245),fill='#dbe4f5');dy=428;wy=457
  d.text((240,dy),'11月9日  周一',font=f(19),fill='#d4dbea',anchor='mm');d.text((240,wy),'上海  23°C  多云',font=f(20),fill='#c3cedf',anchor='mm')
  im.save(APP/('watchface-'+name+'-preview.png'))

def augment():
 layout=json.loads((RES/'screens/main.json').read_text());old=layout['children'];flip=next((n for n in old if n['id']=='flip'),None)
 if flip is None:flip=group('flip',old)
 dial=art();analog=[image('dial','metal_dial',70,70,340,340)]
 for name,length,width,color in [('hour',93,7,'#d7e1f4'),('minute',133,4,'#ecf3ff'),('second',145,2,'#eb725f')]:
  n=node('line',name,70,70,340,340);n['style'].update(lineWidth=width,lineColor=color);n['lineProps']={'points':[{'x':170,'y':190 if name=='second' else 180},{'x':170,'y':170-length}]};n['bindings']={'lineProps.points':'points'};analog.append(n)
 hub=node('container','hub',235,235,10,10);hub['style'].update(bgColor='#dbe4f5',bgOpacity=255,radius=5);analog.append(hub)
 companion,status,pager,modern=modern_widgets()
 hit=node('container','swipe',0,35,480,410);hit['commonProps'].update(clickable=True,pressLock=True);hit['events']=[{'type':'pressed','action':'facePress'},{'type':'released','action':'faceRelease'},{'type':'pressLost','action':'faceCancel'}]
 layout['children']=[flip,group('analog',analog),group('companion',companion),status,pager,hit];write(RES/'screens/main.json',layout)
 idx=json.loads((RES/'images/index.json').read_text());idx['images']=[i for i in idx['images'] if i['id'] not in ['metal_dial','cat_scene'] and not i['id'].startswith(('cat_','clock_','icon_'))]+[dial]+modern
 for i in idx['images']:
  if i['id']=='launcher_icon':
   src=ROOT/'themes/cartoon-q-v1/launcher-optimized/local.flipclock.bin';shutil.copyfile(src,RES/'images/launcher_icon.bin');i['src']='launcher_icon.bin'
 write(RES/'images/index.json',idx)
 manifest=json.loads((APP/'src/manifest.json').read_text());manifest['package']['version']='0.2.5'
 for service,version in [('Wifi','0.8.2'),('Http','0.8.2'),('DeviceModes','0.1.0')]:
  if not any(s['name']==service for s in manifest['services']):manifest['services'].append({'name':service,'version':version})
 write(APP/'src/manifest.json',manifest)
 previews()
 from cat_animation import export
 export()
 shutil.copyfile(APP/'watchface-cat-night-preview.png',APP/'watchface-cat-preview.png')
 write(APP/'package.json',{'name':'local-flip-clock','version':'0.2.5','private':True})
 root=json.loads((RES/'root.json').read_text());root['version']='0.2.5';write(RES/'root.json',root)
if __name__=='__main__':augment()
