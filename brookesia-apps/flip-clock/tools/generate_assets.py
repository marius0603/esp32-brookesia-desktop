"""Draw native split-flap faces and layout; no external images or fonts are embedded."""
import json
from pathlib import Path
import shutil
from PIL import Image, ImageDraw, ImageFont

APP=Path(__file__).resolve().parents[1]
RES=APP/'src/res'
for folder in ('images','screens','flows'):(RES/folder).mkdir(parents=True,exist_ok=True)
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
images=[]
for size,w,h,font_size in [('big',92,152,128)]:
    font=ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf',font_size)
    for digit in '0123456789-':
        face=Image.new('RGB',(w,h));draw=ImageDraw.Draw(face)
        for y in range(h):
            color=tuple(int(c*(1-y/h*.18)) for c in (37,40,46))
            draw.line((0,y,w,y),fill=color)
        box=draw.textbbox((0,0),digit,font=font)
        draw.text(((w-(box[2]-box[0]))/2-box[0],(h-(box[3]-box[1]))/2-box[1]),digit,font=font,fill='#f3eddc')
        half=(h-2)//2
        for part,rect in [('top',(0,0,w,half)),('bottom',(0,half+2,w,h))]:
            id=f'{size}_{part}_{digit}';face.crop(rect).save(RES/'images'/f'{id}.png')
            images.append({'id':id,'src':id+'.png','width':w,'height':half})
icon=Image.new('RGB',(92,92),'#101218');d=ImageDraw.Draw(icon)
d.rounded_rectangle((8,19,84,73),radius=9,fill='#292d36')
f=ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf',38)
d.text((12,23),'12',font=f,fill='#f3eddc');d.text((51,23),'34',font=f,fill='#f3eddc')
d.line((9,46,83,46),fill='#08090c',width=2);icon.save(RES/'images/launcher_icon.png')
images.append({'id':'launcher_icon','src':'launcher_icon.png','width':92,'height':92})
write(RES/'images/index.json',{'type':'imageSet','images':images})
def absolute(x,y,w,h):return {'mode':'absolute','x':x,'y':y,'width':w,'height':h}
def picture(id,x,y,w,h,src,flap=False):
    n={'type':'image','id':id,'placement':absolute(x,y,w,h),'style':{'opacity':0 if flap else 255},'imageProps':{'src':'${image.'+src+'}','innerAlign':'stretch'}}
    if flap:n['bindings']={'placement.y':'y','placement.height':'height','style.opacity':'opacity'}
    return n
children=[]
for i,(x,y,w,h) in enumerate([(34,164,92,152),(134,164,92,152),(254,164,92,152),(354,164,92,152)]):
    size='big' if i<4 else 'small';half=(h-2)//2
    children.append({'type':'container','id':'d'+str(i),'placement':absolute(x,y,w,h),'commonProps':{'scrollable':False,'clickable':False},'style':{'bgColor':'#0a0b0e','borderColor':'#30333b','borderWidth':1,'radius':7,'clipCorner':True,'padding':0},'children':[picture('top',0,0,w,half,f'{size}_top_-'),picture('bottom',0,half+2,w,half,f'{size}_bottom_-'),picture('flap',0,0,w,half,f'{size}_top_-',True)]})
for i,y in enumerate((211,259)):
    children.append({'type':'container','id':'colon'+str(i),'placement':absolute(235,y,10,10),'style':{'bgColor':'#c7c1b1','radius':5,'borderWidth':0,'padding':0},'commonProps':{'clickable':False}})
write(RES/'screens/main.json',{'type':'viewScreen','id':'main','commonProps':{'scrollable':False},'style':{'bgColor':'#08090c','padding':0},'children':children})
write(RES/'root.json',{'version':'0.1.1','assets':['images/index.json','screens/main.json','flows/main.json']})
write(RES/'flows/main.json',{'type':'screenFlow','id':'main','screens':['main'],'initial':'main'})
shutil.copy2(APP.parent/'codex-quota/src/res/profile.json',RES/'profile.json')
(APP/'brookesia.config.js').write_text((APP.parent/'codex-quota/brookesia.config.js').read_text(encoding='utf-8').replace("convertImages: 'res/images'",'convertImages: false'),encoding='utf-8')
write(APP/'package.json',{'name':'local-flip-clock','version':'0.1.1','private':True})
write(APP/'src/manifest.json',{'package':{'id':'local.flipclock','name':{'en':'Flip Clock','zh_CN':'翻页时钟'},'version':'0.1.1','visible':True,'systems':['super']},'runtime':{'type':'JavaScript','entry':'app/main.js','resource_dir':'res','arguments':[]},'services':[{'name':'SNTP','version':'0.8.2'},{'name':'Storage','version':'0.8.3'}]})
preview=Image.new('RGB',(480,480),'#08090c')
for i,node in enumerate(children[:4]):
    value='2034'[i];size='big' if i<4 else 'small';p=node['placement'];half=(p['height']-2)//2
    for part,dy in [('top',0),('bottom',half+2)]:preview.paste(Image.open(RES/'images'/f'{size}_{part}_{value}.png'),(p['x'],p['y']+dy))
d=ImageDraw.Draw(preview)
for y in (211,259):d.ellipse((235,y,245,y+10),fill='#c7c1b1')
preview.save(APP/'preview.png')
print(f'Generated {len(images)} images')
