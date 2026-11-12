"""Package the SD maze UI, original geometric game marks and offline cues."""
import hashlib,json,math,shutil,struct,wave,subprocess
from pathlib import Path
from PIL import Image,ImageDraw
from build_learning_packages import archive
from runtime_paths import find_node
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'brookesia-apps/gravity-maze';SRC=APP/'src'
def write(name,data):
 p=SRC/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def rect(id,x,y,w,h,color='#94b181',hidden=False):
 return {'type':'container','id':id,'placement':{'mode':'absolute','x':x,'y':y,'width':w,'height':h},'commonProps':{'scrollable':False,'clickable':False,'hidden':hidden},'style':{'padding':0,'borderWidth':0,'radius':3,'bgColor':color},'bindings':{'placement.x':'x','placement.y':'y','placement.width':'w','placement.height':'h','style.bgColor':'bg','commonProps.hidden':'hidden'}}
def label(id,text,x,y,w,h,size=20):
 return {'type':'label','id':id,'placement':{'mode':'absolute','x':x,'y':y,'width':w,'height':h},'commonProps':{'scrollable':False},'style':{'font':'${font.zh_CN}','fontSize':size,'textColor':'#584734','textAlign':'center','padding':0,'bgOpacity':0,'borderWidth':0},'labelProps':{'text':text},'bindings':{'style.textColor':'ink'}}
def button(id,text,x,y,w,h=42):
 o=rect(id,x,y,w,h,'#e4ebcf');o['type']='button';o['commonProps']['clickable']=True;o['style']['radius']=16;o['events']=[{'type':'clicked','action':id}];o['children']=[label('label',text,0,(h-28)//2,w,28,21)];return o
def image(id,asset,x,y,w,h):
 o=rect(id,x,y,w,h);o['type']='image';o['style']['bgOpacity']=0;o['imageProps']={'src':'${image.'+asset+'}','innerAlign':'contain'};return o
def main():
 version=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps']['local.gravitymaze']
 for folder in ['app','res/images','res/audio','data']:(SRC/folder).mkdir(parents=True,exist_ok=True)
 (SRC/'app/main.js').write_text((APP/'engine.js').read_text(encoding='utf-8')+'\n'+(APP/'controller.js').read_text(encoding='utf-8'),encoding='utf-8')
 # Reuse the existing mascot unchanged. No account or phone data in this pack.
 shutil.copyfile(ROOT/'phone-remote/android/res/mipmap-mdpi/ic_launcher.png',SRC/'res/images/pony.png')
 shutil.copyfile(ROOT/'phone-remote/android/res/mipmap-xhdpi/ic_launcher.png',SRC/'res/images/launcher_icon.png')
 star=Image.new('RGBA',(48,48));d=ImageDraw.Draw(star);points=[]
 for i in range(10):a=i*math.pi/5-math.pi/2;r=22 if i%2==0 else 10;points.append((24+math.cos(a)*r,24+math.sin(a)*r))
 d.polygon(points,fill='#efb948');star.save(SRC/'res/images/star.png')
 home=Image.new('RGBA',(48,48));d=ImageDraw.Draw(home);d.rounded_rectangle((5,5,43,43),8,fill='#e4ebcf');d.polygon([(10,23),(24,11),(38,23)],fill='#93694c');d.rectangle((14,22,34,37),fill='#f5cb82');d.rounded_rectangle((21,27,28,38),2,fill='#93694c');home.save(SRC/'res/images/home.png')
 for name,notes in [('star',[(880,.10),(1175,.10)]),('win',[(659,.13),(880,.13),(1047,.15),(1319,.22)])]:
  pcm=[]
  for freq,duration in notes:
   count=round(16000*duration)
   for i in range(count):env=min(1,i/160,(count-i)/300);pcm.append(round(4500*env*math.sin(2*math.pi*freq*i/16000)))
  with wave.open(str(SRC/'res/audio'/f'{name}.wav'),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(struct.pack('<'+'h'*len(pcm),*pcm))
 manifest={'package':{'id':'local.gravitymaze','name':{'en':'Pony Maze','zh_CN':'小马迷宫'},'version':version,'visible':True,'systems':['super']},'runtime':{'type':'JavaScript','entry':'app/main.js','resource_dir':'res','arguments':[]},'services':[{'name':'AutoRotation','version':'0.1.2'},{'name':'Storage','version':'0.8.3'},{'name':'DeviceModes','version':'0.1.0'},{'name':'ChildMode','version':'0.1.0'},{'name':'LearningAudio','version':'0.1.1'}]}
 write('manifest.json',manifest);write('res/profile.json',{'root':'root.json','icon_id':'launcher_icon','screen_flows':[{'screen_flow':'main','layer':'AppDefault'}]})
 write('res/root.json',{'version':version,'assets':['images/index.json','templates.json','screens/main.json','flows/main.json']});write('res/flows/main.json',{'type':'screenFlow','id':'main','screens':['main'],'initial':'main'})
 imgs=[]
 for id in ['pony','launcher_icon','star','home']:
  p=SRC/'res/images'/f'{id}.png';im=Image.open(p);imgs.append({'id':id,'src':p.name,'width':im.width,'height':im.height})
 write('res/images/index.json',{'type':'imageSet','images':imgs});node=rect('wall',0,0,8,8);node.pop('id');write('res/templates.json',{'type':'viewTemplate','id':'maze_wall','node':node})
 world=rect('world',0,0,324,324);world['style']['bgOpacity']=0
 world['children']=[image('home','home',260,260,40,40)]+[image('star'+str(i),'star',0,0,34,34) for i in range(3)]+[rect('dot'+str(i),0,0,10,10,'#efb948',True) for i in range(4)]+[image('pony','pony',0,0,44,44)]
 mini=rect('map',242,8,76,76,'#e4ebcf',True);mini['children']=[rect('goal',60,60,4,4,'#584734'),rect('marker',4,4,6,6,'#efb948')]
 viewport=rect('viewport',78,82,324,324,'#eff1d7');viewport['children']=[world,mini]
 finish=rect('finish',30,90,420,300,'#fbf3e1',True);finish['style']['radius']=24;finish['children']=[label('title','小马到家了！',20,48,380,44,32),label('note','谢谢你陪它慢慢探索',20,116,380,36,22),button('next','下一关',74,190,272,54)]
 # Action bubbling uses "next" declared on the nested finish button.
 root=rect('main',0,0,480,480,'#fbf3e1');root['type']='viewScreen';root['style']['radius']=0;root['children']=[label('title','小马迷宫',36,22,230,32,25),label('count','星星 0 / 3',266,28,130,28,19),button('pause','暂停',394,22,62,38),label('status','轻轻倾斜，带小马回家',42,57,396,24,17),viewport,button('hint','提示',78,416,148),button('start','开始找家',254,416,148),finish]
 write('res/screens/main.json',root)
 for test in ['engine.test.cjs','controller.test.cjs']:subprocess.run([find_node(),str(APP/'tests'/test)],check=True)
 name=f'packages/apps/local.gravitymaze.debug.{version}.bpk';digest=archive(ROOT/name,{p.relative_to(SRC).as_posix():p.read_bytes() for p in SRC.rglob('*') if p.is_file() and '/data/' not in p.as_posix()});p=ROOT/'packages/SHA256.json';hashes=json.loads(p.read_text(encoding='utf-8'));hashes[name]=digest
 parent=ROOT/'brookesia-apps/child-mode/src';version=json.loads((parent/'manifest.json').read_text(encoding='utf-8'))['package']['version'];child=f'packages/apps/local.childmode.debug.{version}.bpk';hashes[child]=archive(ROOT/child,{p.relative_to(parent).as_posix():p.read_bytes() for p in parent.rglob('*') if p.is_file()})
 p.write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(name,digest)
if __name__=='__main__':main()
