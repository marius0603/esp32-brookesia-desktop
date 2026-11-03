"""Build native Brookesia JSON screens and presized transparent LVGL artwork."""
import json,struct,sys
from pathlib import Path
from array import array
ROOT=Path(__file__).resolve().parents[3];APP=ROOT/'brookesia-apps/radio';RES=APP/'src/res'
sys.path.insert(0,str(ROOT/'tools'))
from build_wallpaper_render import rle_pixels
from PIL import Image
def write(name,value):
 p=RES/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def native(name,size):
 image=Image.open(RES/'images'/name).convert('RGBA').resize((size,size),Image.Resampling.LANCZOS)
 rgb=image.convert('RGB').tobytes();alpha=image.getchannel('A').tobytes();assert min(alpha)==0 and max(alpha)==255
 pixels=array('H',(((r>>3)<<11)|((g>>2)<<5)|(b>>3) for r,g,b in zip(rgb[0::3],rgb[1::3],rgb[2::3])))
 if sys.byteorder!='little':pixels.byteswap()
 raw=pixels.tobytes()+alpha;encoded=rle_pixels(raw)
 dest=Path(name).stem+'.bin';(RES/'images'/dest).write_bytes(struct.pack('<BBHHHHH',0x19,0x14,8,size,size,size*2,0)+struct.pack('<III',1,len(encoded),len(raw))+encoded)
 return dest
def base(kind,id,x,y,w,h):return dict(type=kind,id=id,placement=dict(mode='absolute',x=x,y=y,width=w,height=h),commonProps=dict(scrollable=False),style=dict(padding=0,borderWidth=0,bgOpacity=0))
def label(id,text,x,y,w,h,size=22,color='#573d30',align='center'):
 n=base('label',id,x,y,w,h);n['style'].update(font='${font.zh_CN}',fontSize=size,textColor=color,textAlign=align);n['labelProps']=dict(text=text);return n
def button(id,text,x,y,w,h,action,size=22,bg='#fffaf1'):
 n=base('button',id,x,y,w,h);n['style'].update(bgOpacity=255,bgColor=bg,borderWidth=1,borderColor='#e1cdb5',radius=20)
 n['bindings']={'style.bgColor':'bg','commonProps.hidden':'hidden'};n['events']=[dict(type='clicked',action=action)];n['children']=[label('label',text,0,max(0,(h-size-8)//2),w,size+10,size)];return n
def panel(id,hidden=False):
 n=base('container',id,0,0,480,480);n['commonProps'].update(hidden=hidden);n['bindings']={'commonProps.hidden':'hidden'};n['children']=[];return n
def main():
 images=[]
 for id,name,size in [('launcher_icon','launcher_icon.png',92),('radio_art','radio_art.png',166)]:images.append(dict(id=id,src=native(name,size),width=size,height=size,preload=True))
 write(Path('images/index.json'),dict(type='imageSet',images=images))
 player=panel('player');c=player['children']
 c.extend([label('brand','小马电台',52,31,220,40,27,align='left'),label('connection','Wi-Fi',310,41,120,24,15,color='#638074')])
 art=base('image','art',157,73,166,166);art['imageProps']={'src':'${image.radio_art}','innerAlign':'contain'};c.append(art)
 c.extend([button('favorite','收藏',362,159,74,44,'favorite',17),label('title','苏州儿童广播',42,231,396,44,30),label('meta','中文 · 亲子广播，按节目表播出',42,280,396,28,16,color='#87715e'),
  button('previous','上一台',64,320,102,64,'previous',22),button('toggle','播放',180,310,120,82,'toggle',27,'#dc9c55'),button('next','下一台',314,320,102,64,'next',22),
  label('status','准备播放',42,400,396,25,17,color='#87715e'),label('volume','音量 --%',80,426,320,22,16,color='#87715e'),
  button('stations','选频道',106,451,126,31,'stations',20,'#fff6e8'),button('timer','定时',248,451,126,31,'timer',20,'#fff6e8')])
 station=panel('stations',True);c=station['children'];c.extend([label('title','选频道',140,35,200,40,27),button('back','返回',42,34,82,42,'back',20,'#fff6e8')])
 for i,name in enumerate(['儿童','音乐','资讯','收藏']):c.append(button('cat'+str(i),name,42+i*101,95,94,42,'cat'+str(i),21,'#e5ad70' if i==0 else '#f4e7d4'))
 for i in range(3):
  row=button('row'+str(i),'',42,157+i*89,396,76,'row'+str(i));row['children']=[label('symbol','童',14,15,48,47,26,color='#6d805f'),label('name','频道',74,9,302,30,23,align='left'),label('sub','频道说明',74,43,302,22,14,color='#937b65',align='left')];c.append(row)
 c.append(button('footer','中文优先 · 英语已标注',62,438,356,36,'listNext',16,'#fff6e8'))
 timer=panel('timer',True);c=timer['children'];c.extend([label('title','睡眠定时',140,35,200,40,27),button('back','返回',42,34,82,42,'timerBack',20,'#fff6e8'),label('sub','到时停止播放，陪你安心入睡',52,94,376,30,19,color='#87715e'),label('moon','晚安电台',100,149,280,45,30,color='#b47f4a')])
 for i,minutes in enumerate([0,15,30,45]):c.append(button('choice'+str(i),'关闭' if not minutes else str(minutes)+' 分钟',65+(i%2)*182,226+(i//2)*84,168,70,'choice'+str(i),28))
 c.extend([label('note','持续收听，不自动停止',45,384,390,25,16,color='#937b65'),button('confirm','确定',144,418,192,46,'timerConfirm',25,'#dca05e')])
 # Keep all three pages within the rounded panel's vertical touch safe area.
 # Only move top-level content; child coordinates remain relative to buttons.
 for page in [player,station,timer]:
  for child in page['children']:child['placement']['y']-=16
 screen=dict(type='viewScreen',id='main',commonProps=dict(scrollable=False),style=dict(bgColor='#fff6e8',padding=0,borderWidth=0),children=[player,station,timer]);write(Path('screens/main.json'),screen)
 write(Path('flows/main.json'),dict(type='screenFlow',id='main',screens=['main'],initial='main'))
 write(Path('root.json'),dict(version='0.1.0',assets=['images/index.json','screens/main.json','flows/main.json']))
 write(Path('profile.json'),dict(root='root.json',icon_id='launcher_icon',screen_flows=[dict(screen_flow='main',layer='AppDefault')]))
 print('Built device layout and transparent RGB565A8/RLE radio assets')
if __name__=='__main__':main()
