"""Generate theme bindings for the three audio apps; rerun after UI generators."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    for folder,handle,state_name in [('nursery-songs','device','d'),('audiobook','modes','sound'),('radio','modes','mode')]:
        src=ROOT/'brookesia-apps'/folder/'src'
        layout=src/'res/screens/main.json'
        doc=json.loads(layout.read_text(encoding='utf-8'));entries=[]
        def visit(node,parent=''):
            path=parent+'/'+node['id']
            for prop,value in node.get('style',{}).items():
                if not prop.endswith('Color') or not isinstance(value,str) or not value.startswith('#'):continue
                key=node.get('bindings',{}).get('style.'+prop,'audioTheme'+prop)
                node.setdefault('bindings',{})['style.'+prop]=key
                role='text' if 'text' in prop.lower() else 'border' if 'border' in prop.lower() else 'accent' if any(k in prop.lower() for k in ('selected','indicator')) else 'root' if not parent else 'button' if node['type'] in ('button','dropdown') else 'panel'
                entries.append([path,key,role])
            for child in node.get('children',[]):visit(child,path)
        visit(doc)
        layout.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        script=src/'app/main.js';code=script.read_text(encoding='utf-8')
        if '// AUDIO_THEME_BEGIN' in code:
            a=code.index('// AUDIO_THEME_BEGIN');b=code.index('// AUDIO_THEME_END',a)+len('// AUDIO_THEME_END\n');code=code[:a]+code[b:]
        helper='''// AUDIO_THEME_BEGIN
let audioThemeDark=false,audioThemeIndex=-1,audioThemeCore;
const audioThemeNodes=ENTRIES;
function audioThemeColor(value){
 const selected=['#e8c477','#e5ad70','#ffedcf','#ffebc7'].includes(value);
 return selected?(audioThemeDark?'#715d3c':'#e8c477'):(audioThemeDark?'#27364b':'#fffaf1');
}
function applyAudioTheme(mode){
 if(!audioThemeCore)audioThemeCore=brookesia.start_service('SystemCore');
 const index=call(audioThemeCore,'GetEnvironment').theme_id==='dark'?1:0;
 if(audioThemeIndex===index&&cache.__audioTheme)return;
 audioThemeIndex=index;audioThemeDark=index===1;cache={};
 const palette=audioThemeDark?{root:'#101723',panel:'#192436',button:'#27364b',text:'#f6ecd9',border:'#52647c',accent:'#b99b65'}:{root:'#f4ebdd',panel:'#fff5e6',button:'#fffaf1',text:'#60442f',border:'#c8b18c',accent:'#d6ad6e'};
 for(const entry of audioThemeNodes)call(gui,'SetBinding',{Path:entry[0],Key:entry[1],Value:palette[entry[2]]});
 cache.__audioTheme=true;
 if(typeof view!=='undefined'&&view==='timer')renderTimer();
 if(typeof screen!=='undefined'&&screen==='timer')renderTimer();
 if(typeof screen!=='undefined'&&screen==='stations')renderList();
}
// AUDIO_THEME_END
'''.replace('ENTRIES',json.dumps(entries,separators=(',',':')))
        pos=code.index('function call(');code=code[:pos]+helper+code[pos:]
        if folder!='audiobook':code=code.replace("function bind(path,key,value){value=String(value);","function bind(path,key,value){if(key==='bg')value=audioThemeColor(value);value=String(value);")
        needle="const "+state_name+"=call("+handle+",'GetState');"
        if needle+'applyAudioTheme' not in code:code=code.replace(needle,needle+'applyAudioTheme('+state_name+');')
        script.write_text(code,encoding='utf-8')

if __name__=='__main__':main()
