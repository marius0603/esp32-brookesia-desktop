"""Generate the small, code-drawn voice assistant UI and launcher icon."""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'brookesia-apps/voice-assistant'
SRC = APP / 'src'

def write(path, data):
    target = APP / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def label(id, text, x, y, width, height, size=20, color='#e7f1ff'):
    return {'type':'label','id':id,'placement':{'x':x,'y':y,'width':width,'height':height},
            'style':{'font':'${font.zh_CN}','fontSize':size,'textColor':color,'textAlign':'center'},
            'labelProps':{'text':text}}

def button(id, text, x, width, color='#243955'):
    return {'type':'button','id':id,'placement':{'x':x,'y':0,'width':width,'height':48},
            'style':{'bgColor':color,'radius':16,'padding':0},
            'layout':{'type':'flex','mainAlign':'center','crossAlign':'center'},
            'events':[{'type':'clicked','action':id}],
            'children':[{'type':'label','id':'label','style':{'font':'${font.zh_CN}','fontSize':21,'textColor':'#ffffff'},'labelProps':{'text':text}}]}

def row(id, y, children):
    return {'type':'container','id':id,'placement':{'x':70,'y':y,'width':340,'height':48},
            'commonProps':{'scrollable':False},'style':{'bgOpacity':0,'padding':0,'borderWidth':0},'children':children}

write('package.json', {'name':'local.voiceassistant','version':'0.1.0','private':True,'scripts':{'build':'brookesia build'}})
(APP/'brookesia.config.js').write_text("module.exports = {cli:{sourceRoot:'src',outputPath:'build',releasePath:'dist',signRoot:'sign'},convertImages:false};\n", encoding='utf-8')
write('src/manifest.json', {'package':{'id':'local.voiceassistant','name':{'en':'Voice Assistant','zh_CN':'智能助手'},'version':'0.1.0','visible':True,'systems':['super']},
      'runtime':{'type':'JavaScript','entry':'app/main.js','resource_dir':'res','arguments':[]},
      'services':[{'name':'VoiceAssistant','version':'0.1.0'},{'name':'AudioPlayback','version':'0.8.2'},{'name':'Audiobook','version':'0.1.0'}]})
write('src/res/profile.json', {'root':'root.json','icon_id':'launcher_icon','screen_flows':[{'screen_flow':'main','layer':'AppDefault'}]})
write('src/res/root.json', {'version':'0.1.0','assets':['images/index.json','screens/main.json','flows/main.json']})
write('src/res/flows/main.json', {'type':'screenFlow','id':'main','screens':['main'],'initial':'main'})
children=[label('title','智能助手',130,35,220,36,28),label('status','正在连接小智',65,80,350,44,18,'#9abde0'),
          label('code','',100,121,280,50,40,'#54d9d1'),label('user','',65,173,350,46,18,'#9abde0'),
          label('answer','点击说话，再次点击发送',65,225,350,94,22)]
children.append({'type':'container','id':'meter','placement':{'x':100,'y':316,'width':280,'height':5},
                 'commonProps':{'scrollable':False},'style':{'bgColor':'#1b2c41','padding':0,'borderWidth':0,'radius':3},
                 'children':[{'type':'container','id':'fill','placement':{'x':0,'y':0,'width':0,'height':5},
                              'commonProps':{'scrollable':False},'style':{'bgColor':'#54d9d1','padding':0,'borderWidth':0,'radius':3},
                              'bindings':{'placement.width':'width'}}]})
children += [row('controls',335,[button('quieter','-',0,78),button('talk','说话',90,160,'#167f85'),button('louder','+',262,78)]),
             row('tools',391,[button('connect','连接',0,85),button('test','录音测试',96,148),button('cancel','停止',255,85)]),
             label('volume','音量 --%',140,445,200,22,14,'#9abde0')]
write('src/res/screens/main.json', {'type':'viewScreen','id':'main','commonProps':{'scrollable':False},
                                 'style':{'bgColor':'#0b1422','padding':0},'children':children})
icon=Image.new('RGBA',(96,96),(0,0,0,0));draw=ImageDraw.Draw(icon)
draw.rounded_rectangle((4,4,92,92),radius=24,fill='#167f85')
draw.rounded_rectangle((37,17,59,56),radius=11,fill='#e7faff')
draw.arc((27,30,69,70),0,180,fill='#e7faff',width=5)
draw.line((48,70,48,79),fill='#e7faff',width=5);draw.line((35,80,61,80),fill='#e7faff',width=5)
(SRC/'res/images').mkdir(parents=True,exist_ok=True)
icon.save(SRC/'res/images/launcher_icon.png',optimize=True)
# Match the toolkit's established image resource shape.
image_index=json.loads((ROOT/'brookesia-apps/audiobook/src/res/images/index.json').read_text(encoding='utf-8'))
image_index['images'][0].update(width=96,height=96)
write('src/res/images/index.json',image_index)
print(APP)
