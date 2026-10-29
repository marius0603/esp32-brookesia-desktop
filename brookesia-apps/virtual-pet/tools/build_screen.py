"""Build the pet screen and its schedule sheet using the established JSON UI."""
import json
from pathlib import Path
APP=Path(__file__).resolve().parents[1]
def place(x,y,w,h):return {'mode':'absolute','x':x,'y':y,'width':w,'height':h}
def label(id,text,x,y,w,h,size=24,align='center',color='#674536'):
 return {'type':'label','id':id,'placement':place(x,y,w,h),'style':{'font':'${font.zh_CN}','fontSize':size,'textColor':color,'textAlign':align},'labelProps':{'text':text}}
def button(id,text,x,y,w=112,action=None):
 return {'type':'button','id':id,'placement':place(x,y,w,44),'commonProps':{'scrollable':False},'style':{'bgColor':'#eedac4','radius':18,'padding':0,'borderWidth':0},'layout':{'type':'flex','mainAlign':'center','crossAlign':'center'},'events':[{'type':'clicked','action':action or id}],'children':[{'type':'label','id':'label','style':{'font':'${font.zh_CN}','fontSize':24,'textColor':'#674536'},'labelProps':{'text':text}}]}
def container(id,hidden,children):
 return {'type':'container','id':id,'placement':place(0,0,480,480),'commonProps':{'hidden':hidden,'scrollable':False},'bindings':{'commonProps.hidden':'hidden'},'style':{'bgOpacity':0,'padding':0,'borderWidth':0},'children':children}
def main():
 def picture(id,opacity):return {'type':'image','id':id,'placement':place(0,0,320,320),'commonProps':{'clickable':False,'scrollable':False},'style':{'opacity':opacity},'bindings':{'style.opacity':'opacity'},'imageProps':{'src':'${image.pet_idle_0}','innerAlign':'center'}}
 pet={'type':'container','id':'pet','placement':place(80,80,320,320),'style':{'bgOpacity':0,'padding':0,'borderWidth':0},'commonProps':{'clickable':True,'scrollable':False},'bindings':{'placement.y':'y'},'events':[{'type':'clicked','action':'petTap'}],'children':[picture('base',255),picture('blend',255)]}
 home=container('home',False,[pet,button('feed','喂食',54,404),button('touch','陪伴',184,404,action='pet'),button('schedule','作息',314,404)])
 schedule=container('schedule',True,[label('heading','小栗的作息',60,100,360,40,30),label('meal0','早餐   07:30',80,159,320,36),label('meal1','午餐   12:00',80,207,320,36),label('meal2','晚餐   18:30',80,255,320,36),label('sleep','睡觉   22:00 - 07:00',60,308,360,36),button('sleepPreview','看看睡觉',67,390,166),button('back','返回',247,390,166)])
 screen={'type':'viewScreen','id':'main','commonProps':{'scrollable':False},'style':{'bgColor':'#fff7e8','padding':0},'children':[home,schedule,label('title','小栗',48,32,160,44,34,'left'),label('clock','--:--',310,38,120,38,28,'right'),label('status','陪你一起',130,76,220,32,22,color='#497d78'),label('hint','',40,451,400,24,16,color='#8d7966')]}
 (APP/'src/res/screens').mkdir(parents=True,exist_ok=True)
 (APP/'src/res/screens/main.json').write_text(json.dumps(screen,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
