"""Generate the native circular-screen layout and vector launcher artwork."""
import json
from pathlib import Path

APP=Path(__file__).resolve().parents[1]
SRC=APP/'src'

def write(name,value):
    p=SRC/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def place(x,y,w,h):return dict(mode='absolute',x=x,y=y,width=w,height=h)
def label(id,text,x,y,w,h=36,size=24):
    return dict(type='label',id=id,placement=place(x,y,w,h),style=dict(font='${font.audiobook_title}',fontSize=size,textColor='#60442f',textAlign='center'),labelProps=dict(text=text))
def button(id,text,x,y,w,h=58,action=None,color='#fff6e2',size=26):
    return dict(type='button',id=id,placement=place(x,y,w,h),commonProps=dict(scrollable=False),style=dict(bgColor=color,borderColor='#c8b18c',borderWidth=1,radius=18,padding=0),bindings={'style.bgColor':'bg','commonProps.hidden':'hidden'},layout=dict(type='flex',mainAlign='center',crossAlign='center'),events=[dict(type='clicked',action=action or id)],children=[label('label',text,0,0,w-12,36,size)|{'placement':dict(width=w-12,height=36)}])
def panel(id,children):
    return dict(type='container',id=id,placement=place(0,54,400,340),commonProps=dict(scrollable=False,hidden=id!='player'),style=dict(bgOpacity=0,borderWidth=0,padding=0),bindings={'commonProps.hidden':'hidden'},children=children)

def main():
    write('manifest.json',{'package':{'id':'local.nurserysongs','name':{'en':'Nursery Songs','zh_CN':'儿歌'},'version':'0.1.0','visible':True,'systems':['super']},'runtime':{'type':'JavaScript','entry':'app/main.js','resource_dir':'res','arguments':[]},'services':[{'name':'Audiobook','version':'0.1.0'},{'name':'SystemCore','version':'0.8.3'},{'name':'DeviceModes','version':'0.1.0'}]})
    write('res/root.json',{'version':'0.1.0','assets':['images/index.json','screens/main.json','flows/main.json']})
    write('res/profile.json',{'root':'root.json','icon_id':'launcher_icon','screen_flows':[{'screen_flow':'main','layer':'AppDefault'}]})
    write('res/flows/main.json',{'type':'screenFlow','id':'main','screens':['main'],'initial':'main'})
    header=dict(type='container',id='header',placement=place(0,0,400,48),commonProps=dict(scrollable=False),style=dict(bgOpacity=0,borderWidth=0,padding=0),children=[label('volume','音量 --%',22,6,232,36,22),button('lock','锁屏',270,0,110,46,'lock',size=22)])
    player=panel('player',[
        label('title','儿歌',12,4,376,50,34),label('count','暂无歌曲',10,58,380,30,20),
        label('progress','0:00 / 0:00',10,91,380,32,24),label('status','准备播放',10,128,380,30,22),
        button('previous','上一首',8,170,112),button('toggle','播放',126,164,148,70,color='#e8c477',size=30),button('next','下一首',280,170,112),
        button('songs','选歌',8,248,112),button('mode','顺序播放',126,248,148,size=22),button('sleepButton','定时',280,248,112,action='sleep'),
        label('sleep','',10,312,380,26,20)])
    songs=panel('songs',[label('heading','儿歌列表',50,0,300,38,28)]+[button('row'+str(i),'',18,44+i*54,364,48,size=24) for i in range(4)]+[button('prevPage','上一页',18,272,112,48,'listPrev',size=22),label('page','1 / 5',138,279,124,36,22),button('nextPage','下一页',270,272,112,48,'listNext',size=22),button('back','返回',145,326,110,42,size=22)])
    # List's bottom return sits at y=380; total content is within the round
    # display's middle 400px safe band rather than its narrow lower corners.
    songs['placement']['height']=372
    timer=panel('timer',[label('heading','睡眠定时',40,10,320,42,30)]+[button('choice'+str(i),t,34+(i%2)*170,76+(i//2)*72,160,60,size=26) for i,t in enumerate(['关闭','15分钟','30分钟','45分钟'])]+[label('note','最后两分钟渐弱',20,228,360,36,22),button('back','返回',36,278,150,56,'timerBack'),button('confirm','确定',214,278,150,56,'timerConfirm',color='#e8c477')])
    write('res/screens/main.json',dict(type='viewScreen',id='main',commonProps=dict(scrollable=False),style=dict(bgColor='#e8f2e4',borderWidth=0,padding=0),layout=dict(type='flex',mainAlign='center',crossAlign='center'),children=[dict(type='container',id='content',placement=dict(width=400,height=426),style=dict(bgOpacity=0,padding=0,borderWidth=0),commonProps=dict(scrollable=False),children=[])]))
    # Paths must stay /main/header, /main/player etc. Avoid a nested content
    # container: absolute coordinates are centered against the 486px screen.
    screen=json.loads((SRC/'res/screens/main.json').read_text(encoding='utf-8'))
    screen.pop('layout');screen['children']=[header,player,songs,timer]
    for item in screen['children']:
        item['placement']['x']=43;item['placement']['y']+=40
    header['placement']=place(73,48,340,48)
    header['children'][0]['placement']=place(0,6,220,36)
    header['children'][1]['placement']=place(226,0,100,46)
    write('res/screens/main.json',screen)
    write('res/images/index.json',{'type':'imageSet','images':[{'id':'launcher_icon','src':'launcher_icon.png','width':96,'height':96}]})
    svg='''<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">
<g stroke="#60442f" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round">
<rect x="3" y="3" width="90" height="90" rx="23" fill="#e1f0d7"/>
<path d="M25 42L21 17Q31 13 38 36M49 34L51 14Q62 12 64 36" fill="#e3ae78"/>
<path d="M29 37Q44 22 61 38Q78 42 73 64L68 79Q44 91 26 74Q13 58 29 37Z" fill="#f4c892"/>
<path d="M28 40Q28 24 45 26L57 32L50 41L41 35L36 44Z" fill="#a47055"/>
<ellipse cx="48" cy="66" rx="24" ry="14" fill="#ffdfb4"/>
<path d="M33 52Q36 47 39 52M53 51Q56 46 59 51" fill="none"/>
<path d="M40 69Q48 76 56 69" fill="none"/><path d="M34 64h1M61 64h1"/>
<path d="M69 24V43M69 25L83 21V39" fill="none" stroke="#60977c" stroke-width="4"/>
<ellipse cx="65" cy="44" rx="6" ry="4" fill="#79ac8e" stroke="none"/><ellipse cx="79" cy="40" rx="6" ry="4" fill="#79ac8e" stroke="none"/>
<path d="M15 34L17 30M78 69L83 73" stroke="#d4a94f"/>
</g></svg>'''
    (SRC/'res/images/launcher_icon.svg').write_text(svg,encoding='utf-8')
    print('Generated nursery song layout and vector icon; rasterize SVG with sharp.')

if __name__=='__main__':main()
