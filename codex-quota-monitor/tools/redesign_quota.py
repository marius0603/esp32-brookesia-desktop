"""Apply the approved quota card geometry, keeping native images and view paths."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PALETTES={
 'dark':dict(root='#090e17',card='#151e2c',edge='#2a3648',ink='#edf2f8',muted='#a6b4c7',track='#0c1420',gold='#ffd166',mint='#71ddc9',pill='#172a28',status='#91dfbb'),
 'light':dict(root='#f5eddf',card='#fffaf2',edge='#dfd0b7',ink='#453b31',muted='#7d6b58',track='#f0e5d2',gold='#a86c12',mint='#197e70',pill='#e1eddb',status='#35704e')}


def main():
 p=ROOT/'brookesia-apps/codex-quota/src/res/screens/main.json'
 screen=json.loads(p.read_text(encoding='utf-8'));nodes=[]
 def color(n,path,prop,role):
  n.setdefault('style',{})[prop]=PALETTES['dark'][role]
  n.setdefault('bindings',{})['style.'+prop]='theme'+prop
  nodes.append([path,'theme'+prop,role])
 def place(n,x,y,w,h):n['placement']=dict(mode='absolute',x=x,y=y,width=w,height=h)
 def label(id,x,y,w,h,size):
  return dict(type='label',id=id,placement=dict(mode='absolute',x=x,y=y,width=w,height=h),style=dict(font='${font.zh_CN}',fontSize=size,textAlign='left'),labelProps=dict(text=''))
 def block(id,x,y,w,h):return dict(type='container',id=id,placement=dict(mode='absolute',x=x,y=y,width=w,height=h),commonProps=dict(clickable=False,scrollable=False),style=dict(padding=0,borderWidth=0))
 screen.pop('layout',None);color(screen,'/main','bgColor','root')
 sync=screen['children'][0];place(sync,170,25,140,30)
 sync['style'].update(radius=15,borderWidth=0)
 color(sync,'/main/sync','bgColor','pill')
 status=sync['children'][1];status['style']['fontSize']=19;color(status,'/main/sync/status','textColor','status')
 for i,kind in enumerate(('primary','secondary')):
  card=screen['children'][i+1];base='/main/card_'+kind
  place(card,26,78+i*194,428,178)
  for key in ('bgGradientColor','bgGradientDirection'):card['style'].pop(key,None)
  card['style'].update(radius=25,borderWidth=1)
  color(card,base,'bgColor','card');color(card,base,'borderColor','edge')
  old={n['id']:n for n in card['children']}
  title=old['label_'+kind];place(title,22,19,180,36);title['style'].update(fontSize=26);color(title,base+'/'+title['id'],'textColor','ink')
  value=old[kind];place(value,18,36,"wrap",100);value['style'].update(fontSize=72,textAlign='left');value['labelProps']['text']='--';value.setdefault('bindings',{})['style.fontSize']='fontSize'
  role='gold' if i==0 else 'mint';color(value,base+'/'+kind,'textColor',role)
  suffix=label('unit_'+kind,179,80,34,48,32);suffix['labelProps']['text']='%';suffix['bindings']={'placement.x':'x'};color(suffix,base+'/'+suffix['id'],'textColor',role)
  divider=block('divider',214,68,1,42);color(divider,base+'/divider','bgColor','edge')
  clock=block('clock',236,78,16,16);clock['style'].update(bgOpacity=0,borderWidth=1,radius=8)
  color(clock,base+'/clock','borderColor','muted')
  clock['children']=[block('hour',7,3,1,5),block('minute',7,7,5,1)]
  for hand in clock['children']:color(hand,base+'/clock/'+hand['id'],'bgColor','muted')
  days=label('days_'+kind,264,49,148,24,18);color(days,base+'/'+days['id'],'textColor','muted')
  reset=old['reset_'+kind];place(reset,264,73,148,58);reset['style'].update(fontSize=27,textAlign='left');reset['labelProps']['text']='等待同步';reset.setdefault('bindings',{})['style.fontSize']='fontSize';color(reset,base+'/'+reset['id'],'textColor','ink')
  track=old['track_'+kind];place(track,18,137,392,32);track['style'].update(radius=16,borderWidth=0);color(track,base+'/'+track['id'],'bgColor','track')
  for child in track['children']:
   if child['id'].startswith('d'):
    child['placement']['y']=13;color(child,base+'/'+track['id']+'/'+child['id'],'bgColor',role)
   elif child['id']=='pac':child['placement']['y']=1
  card['children']=[title,value,suffix,divider,clock,days,reset,track]
 p.write_text(json.dumps(screen,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 script=ROOT/'brookesia-apps/codex-quota/src/app/main.js';source=script.read_text(encoding='utf-8')
 start,end='// QUOTA_THEME_BEGIN','// QUOTA_THEME_END'
 theme=start+'\nconst themePalettes='+json.dumps(PALETTES,separators=(',',':'))+';\nconst themeNodes='+json.dumps(nodes,separators=(',',':'))+';\n'+end
 if start in source:source=source[:source.index(start)]+theme+source[source.index(end)+len(end):]
 else:source=source.replace('const PAC_TRAVEL=358;','const PAC_TRAVEL=358;\n'+theme)
 script.write_text(source,encoding='utf-8')


if __name__=='__main__':main()
