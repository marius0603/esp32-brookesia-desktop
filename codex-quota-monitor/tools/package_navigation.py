"""Build small original navigation artwork, UI documents and the SD app package."""
import json
import subprocess
import hashlib
import wave
from pathlib import Path
from PIL import Image, ImageDraw
from build_learning_packages import archive
from runtime_paths import find_node
ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'brookesia-apps/navigation'
SRC=APP/'src'

def write(name,data):
 p=SRC/name;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def artwork():
 folder=SRC/'res/images';folder.mkdir(parents=True,exist_ok=True)
 for turn in range(8):
  im=Image.new('RGBA',(640,640));d=ImageDraw.Draw(im);color='#35bfa9'
  points=[(320,530),(320,120),(170,270),(320,120),(470,270)]
  if turn==1:points=[(400,530),(400,280),(130,280),(255,155),(130,280),(255,405)]
  if turn==2:points=[(240,530),(240,280),(510,280),(385,155),(510,280),(385,405)]
  if turn==3:points=[(400,530),(400,360),(160,120),(160,310),(160,120),(350,120)]
  if turn==4:points=[(240,530),(240,360),(480,120),(290,120),(480,120),(480,310)]
  if turn==5:
   d.arc((160,90,480,410),180,360,fill=color,width=48)
   points=[(480,250),(480,520)];d.line([(160,250),(160,490),(65,390),(160,490),(255,390)],fill=color,width=48,joint='curve')
  if turn==6:
   d.rounded_rectangle((125,115,515,515),radius=70,outline=color,width=32)
   points=[(205,325),(295,415),(440,225)]
  if turn==7:
   d.rounded_rectangle((180,85,460,555),radius=45,outline=color,width=32)
   d.line((275,490,365,490),fill=color,width=20)
   d.ellipse((294,180,346,232),fill=color);points=[(320,280),(320,410)]
  d.line(points,fill=color,width=48,joint='curve')
  im.resize((160,160),Image.Resampling.LANCZOS).save(folder/f'turn_{turn}.png')
 im=Image.new('RGBA',(368,368));d=ImageDraw.Draw(im)
 d.rounded_rectangle((8,8,360,360),radius=84,fill='#fff1d6',outline='#674c3b',width=12)
 d.line([(55,280),(120,170),(235,220),(315,95)],fill='#c0d8bb',width=48,joint='curve')
 d.polygon([(189,53),(101,241),(189,209),(276,241)],fill='#36b6a1',outline='#674c3b',width=10)
 im.resize((92,92),Image.Resampling.LANCZOS).save(folder/'launcher_icon.png')

def main():
 artwork()
 write('manifest.json',{'package':{'id':'local.navigation','name':{'en':'Navigation','zh_CN':'小马导航'},'version':'0.2.0','visible':True,'systems':['super']},'runtime':{'type':'JavaScript','entry':'app/main.js','resource_dir':'res','arguments':[]},'services':[{'name':'AudioPlayback','version':'0.8.2'},{'name':'DeviceModes','version':'0.1.0'},{'name':'LearningAudio','version':'0.1.0'}]})
 write('res/profile.json',{'root':'root.json','icon_id':'launcher_icon','screen_flows':[{'screen_flow':'main','layer':'AppDefault'}]})
 write('res/root.json',{'version':'0.2.0','assets':['images/index.json','screens/main.json','flows/main.json']})
 write('res/images/index.json',{'type':'imageSet','images':[{'id':'launcher_icon','src':'launcher_icon.png','width':92,'height':92}]+[{'id':f'turn_{t}','src':f'turn_{t}.png','width':160,'height':160} for t in range(8)]})
 write('res/flows/main.json',{'type':'screenFlow','id':'main','screens':['main'],'initial':'main'})
 def label(id,text,x,y,w,h,size,ink='#edf2f8'):
  return {'type':'label','id':id,'placement':{'mode':'absolute','x':x,'y':y,'width':w,'height':h},'commonProps':{'scrollable':False},'style':{'padding':0,'borderWidth':0,'bgOpacity':0,'font':'${font.zh_CN}','fontSize':size,'textColor':ink,'textAlign':'left'},'labelProps':{'text':text},'bindings':{'style.textColor':'ink','style.fontSize':'size'}}
 children=[label('brand','小马导航',52,32,200,30,26),label('source','手机蓝牙同步',270,36,160,25,18),
  label('status','等待手机连接',52,76,376,28,21),
  {'type':'image','id':'arrow','placement':{'mode':'absolute','x':48,'y':113,'width':160,'height':160},'commonProps':{'hidden':True,'scrollable':False},'imageProps':{'src':'${image.turn_0}'},'bindings':{'commonProps.hidden':'hidden'}},
  label('distance','--',224,130,220,82,52),label('turn','等待导航',224,222,220,38,28,'#71ddc9'),
  label('road','在小马遥控中开启导航同步',52,285,376,74,28),
  {'type':'container','id':'divider','placement':{'mode':'absolute','x':52,'y':368,'width':376,'height':1},'style':{'bgColor':'#2a3648','padding':0,'borderWidth':0},'bindings':{'style.bgColor':'background'}},
  label('details','不使用设备定位，不独立算路',52,382,376,32,23),
  {'type':'button','id':'voice','placement':{'mode':'absolute','x':52,'y':423,'width':190,'height':32},'style':{'bgColor':'#172a28','radius':12,'padding':0,'borderWidth':0},'bindings':{'style.bgColor':'background'},'events':[{'type':'clicked','action':'voice'}],'children':[label('label','语音提示：开',0,3,190,26,19)]},
  label('note','请以手机为准',266,429,164,25,17)]
 # Graphic-first full-screen layout. Existing IDs preserve lifecycle/state bindings.
 by={n['id']:n for n in children}
 for id in ['brand','source','divider','turn','note']:by[id].setdefault('commonProps',{})['hidden']=True
 def place(id,x,y,w,h):by[id]['placement'].update(x=x,y=y,width=w,height=h)
 place('arrow',160,94,160,160);place('distance',65,251,350,83);by['distance']['style']['textAlign']='center'
 place('road',52,339,376,37);by['road']['style'].update(fontSize=22,textAlign='center')
 place('details',52,382,376,29);by['details']['style'].update(fontSize=20,textAlign='center')
 place('status',78,151,324,52);by['status']['style'].update(fontSize=26,textAlign='center');by['status']['bindings']['commonProps.hidden']='hidden'
 place('voice',52,416,166,38);by['voice']['children'][0]['placement'].update(x=0,y=5,width=166,height=28);by['voice']['children'][0]['style'].update(fontSize=20,textAlign='center')
 children.append(label('volume','70%',205,30,140,29,22))
 def bar(id,x,y,w,h):return {'type':'container','id':id,'placement':{'mode':'absolute','x':x,'y':y,'width':w,'height':h},'style':{'bgColor':'#edf2f8','borderWidth':0,'padding':0,'radius':2},'bindings':{'style.bgColor':'foreground','placement.width':'width'}}
 # Original geometric speaker and Bluetooth marks: no dependency on missing font glyphs.
 children.append({'type':'container','id':'bluetooth','placement':{'mode':'absolute','x':57,'y':35,'width':17,'height':24},'style':{'bgOpacity':0,'borderWidth':0,'padding':0},'children':[bar('stem',7,0,3,24),bar('top',9,3,7,3),bar('middle',0,10,16,3),bar('bottom',9,19,7,3)]})
 children.append({'type':'container','id':'speaker','placement':{'mode':'absolute','x':176,'y':34,'width':22,'height':23},'style':{'bgOpacity':0,'padding':0,'borderWidth':0},'children':[bar('body',0,7,8,10),bar('cone',8,3,6,18),bar('wave',18,6,3,12)]})
 children.append({'type':'container','id':'battery','placement':{'mode':'absolute','x':375,'y':37,'width':29,'height':15},'style':{'bgOpacity':0,'borderWidth':2,'borderColor':'#a6b4c7','radius':4,'padding':2},'children':[bar('fill',0,0,21,7)]})
 for id,x,plus in [('minus',262,False),('plus',340,True)]:
  children.append({'type':'button','id':id,'placement':{'mode':'absolute','x':x,'y':416,'width':64,'height':38},'style':{'bgColor':'#162431','radius':14,'borderWidth':0,'padding':0},'bindings':{'style.bgColor':'background'},'events':[{'type':'clicked','action':id}],'children':[bar('h',21,18,22,3)]+([bar('v',31,9,3,22)] if plus else [])})
 write('res/screens/main.json',{'type':'viewScreen','id':'main','commonProps':{'scrollable':False},'style':{'bgColor':'#090e17','padding':0,'borderWidth':0},'bindings':{'style.bgColor':'background'},'children':children})
 subprocess.run([find_node(),str(APP/'tests/main.test.cjs')],check=True)
 audio=SRC/'res/audio';meta=json.loads((audio/'sources.json').read_text(encoding='utf-8'));meta['files']={}
 for turn in range(8):
  for stage in range(3):
   p=audio/f'turn-{turn}-{stage}.wav'
   with wave.open(str(p),'rb') as w:assert w.getnchannels()==1 and w.getsampwidth()==2 and w.getframerate()==16000 and 0<w.getnframes()<16000*20
   meta['files'][p.name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 (audio/'sources.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 files={p.relative_to(SRC).as_posix():p.read_bytes() for p in SRC.rglob('*') if p.is_file()}
 name='packages/apps/local.navigation.debug.0.2.0.bpk';digest=archive(ROOT/name,files)
 p=ROOT/'packages/SHA256.json';hashes=json.loads(p.read_text(encoding='utf-8'));hashes[name]=digest;p.write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(name,digest)
if __name__=='__main__':main()
