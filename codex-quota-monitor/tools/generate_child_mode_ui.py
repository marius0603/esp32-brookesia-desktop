"""Build the child-mode parent panel using existing native controls and theme art."""
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'brookesia-apps/child-mode'
def write(name,data):
    p=APP/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
def label(id,text,x,y,w,h,size=21):
    return {'type':'label','id':id,'placement':{'x':x,'y':y,'width':w,'height':h},
            'style':{'font':'${font.zh_CN}','fontSize':size,'textColor':'#674536','textAlign':'center'},'labelProps':{'text':text}}
def button(id,text,x,y,w=280,h=44):
    return {'type':'button','id':id,'placement':{'x':x,'y':y,'width':w,'height':h},
            'style':{'bgColor':'#f5d7b9','radius':14,'borderWidth':1,'borderColor':'#b88a69','padding':0},
            'events':[{'type':'clicked','action':id}],
            'layout':{'type':'flex','mainAlign':'center','crossAlign':'center'},
            'children':[{'type':'label','id':'label','style':{'font':'${font.zh_CN}','fontSize':21,'textColor':'#674536'},'labelProps':{'text':text}}]}
def group(id,children,hidden=True):
    return {'type':'container','id':id,'placement':{'x':0,'y':0,'width':480,'height':480},
            'commonProps':{'hidden':hidden,'scrollable':False},'bindings':{'commonProps.hidden':'hidden'},
            'style':{'bgOpacity':0,'borderWidth':0,'padding':0},'children':children}
def stepper(prefix,title,y):
    return [button(prefix+'_minus','-',104,y,48),label(prefix,title,158,y+5,164,38),button(prefix+'_plus','+',328,y,48)]

write('package.json',{'name':'local.childmode','version':'0.1.0','private':True,'scripts':{'build':'brookesia build'}})
(APP/'brookesia.config.js').write_text("module.exports={cli:{sourceRoot:'src',outputPath:'build',releasePath:'dist',signRoot:'sign'},convertImages:false};\n",encoding='utf-8')
write('src/manifest.json',{'package':{'id':'local.childmode','name':{'en':'Child Mode','zh_CN':'儿童模式'},'version':'0.1.0','visible':True,'systems':['super']},
    'runtime':{'type':'JavaScript','entry':'app/main.js','resource_dir':'res','arguments':[]},'services':[{'name':'ChildMode','version':'0.1.0'}]})
write('src/res/profile.json',{'root':'root.json','icon_id':'launcher_icon','screen_flows':[{'screen_flow':'main','layer':'AppDefault'}]})
write('src/res/root.json',{'version':'0.1.0','assets':['images/index.json','screens/main.json','flows/main.json']})
write('src/res/flows/main.json',{'type':'screenFlow','id':'main','screens':['main'],'initial':'main'})
gate=[label('dots','',120,137,240,40,32)]
for i,char in enumerate('123456789'):
    gate.append(button('digit'+char,char,104+i%3*94,194+i//3*57,84,48))
gate += [button('erase','删除',104,365,84,48),button('digit0','0',198,365,84,48),button('enter','确定',292,365,84,48),
         label('hint','请由家长操作',130,428,220,25,16)]
control=[button('mode','开启儿童模式',105,126,270),*stepper('volume','音量上限 30%',187),
         *stepper('limit','每日 30 分钟',246),button('apps','允许使用的应用',105,306,270),
         button('time','休息时间 / PIN',105,363,270),button('lock','完成并锁定',140,420,200,36)]
apps=[button('book','听书：允许',105,126,270),button('weather','天气：允许',105,183,270),
      button('clock','时钟：允许',105,240,270),button('assistant','语音助手：关闭',105,297,270),button('back_apps','返回',140,376,200)]
times=[button('night','夜间休息：关闭',105,126,270),*stepper('start','开始 21:00',185),*stepper('end','结束 08:00',242),
       button('reset','重置今日时长',120,299,240),button('change','修改家长 PIN',120,354,240),button('back_time','返回',140,413,200,36)]
children=[group('gate',gate,False),group('control',control),group('apps',apps),group('times',times),
          label('title','儿童模式',120,36,240,40,28),label('status','正在读取设置',65,84,350,40,17)]
write('src/res/screens/main.json',{'type':'viewScreen','id':'main','commonProps':{'scrollable':False},'style':{'bgColor':'#fff2df','padding':0},'children':children})
image_dir=APP/'src/res/images';image_dir.mkdir(parents=True,exist_ok=True)
shutil.copy2(APP/'artwork/child-mode.png',image_dir/'launcher_icon.png')
write('src/res/images/index.json',{'type':'imageSet','images':[{'id':'launcher_icon','src':'launcher_icon.png','width':96,'height':96}]})
print(APP)
