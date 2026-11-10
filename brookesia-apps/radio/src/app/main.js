(function(){'use strict';
const categories=['儿童','音乐','资讯','收藏'],timerOptions=[0,15,30,45];
let gui,storage,audio,volume,modes,wifi,timer,stations=[],current=0,category='儿童',favorites=[],minutes=0,draft=0,page=0,rows=[],hidden=false,screen='player',state={},cache={};
// AUDIO_THEME_BEGIN
let audioThemeDark=false,audioThemeIndex=-1,audioThemeCore;
const audioThemeNodes=[["/main","audioThemebgColor","root"],["/main/player/brand","audioThemetextColor","text"],["/main/player/connection","audioThemetextColor","text"],["/main/player/lockScreen","bg","button"],["/main/player/lockScreen","audioThemeborderColor","border"],["/main/player/lockScreen/label","audioThemetextColor","text"],["/main/player/title","audioThemetextColor","text"],["/main/player/meta","audioThemetextColor","text"],["/main/player/previous","bg","button"],["/main/player/previous","audioThemeborderColor","border"],["/main/player/previous/label","audioThemetextColor","text"],["/main/player/toggle","bg","button"],["/main/player/toggle","audioThemeborderColor","border"],["/main/player/toggle/label","audioThemetextColor","text"],["/main/player/next","bg","button"],["/main/player/next","audioThemeborderColor","border"],["/main/player/next/label","audioThemetextColor","text"],["/main/player/status","audioThemetextColor","text"],["/main/player/volume","audioThemetextColor","text"],["/main/player/stations","bg","button"],["/main/player/stations","audioThemeborderColor","border"],["/main/player/stations/label","audioThemetextColor","text"],["/main/player/timer","bg","button"],["/main/player/timer","audioThemeborderColor","border"],["/main/player/timer/label","audioThemetextColor","text"],["/main/stations/title","audioThemetextColor","text"],["/main/stations/back","bg","button"],["/main/stations/back","audioThemeborderColor","border"],["/main/stations/back/label","audioThemetextColor","text"],["/main/stations/cat0","bg","button"],["/main/stations/cat0","audioThemeborderColor","border"],["/main/stations/cat0/label","audioThemetextColor","text"],["/main/stations/cat1","bg","button"],["/main/stations/cat1","audioThemeborderColor","border"],["/main/stations/cat1/label","audioThemetextColor","text"],["/main/stations/cat2","bg","button"],["/main/stations/cat2","audioThemeborderColor","border"],["/main/stations/cat2/label","audioThemetextColor","text"],["/main/stations/cat3","bg","button"],["/main/stations/cat3","audioThemeborderColor","border"],["/main/stations/cat3/label","audioThemetextColor","text"],["/main/stations/row0","bg","button"],["/main/stations/row0","audioThemeborderColor","border"],["/main/stations/row0/symbol","audioThemetextColor","text"],["/main/stations/row0/name","audioThemetextColor","text"],["/main/stations/row0/sub","audioThemetextColor","text"],["/main/stations/row1","bg","button"],["/main/stations/row1","audioThemeborderColor","border"],["/main/stations/row1/symbol","audioThemetextColor","text"],["/main/stations/row1/name","audioThemetextColor","text"],["/main/stations/row1/sub","audioThemetextColor","text"],["/main/stations/row2","bg","button"],["/main/stations/row2","audioThemeborderColor","border"],["/main/stations/row2/symbol","audioThemetextColor","text"],["/main/stations/row2/name","audioThemetextColor","text"],["/main/stations/row2/sub","audioThemetextColor","text"],["/main/stations/footer","bg","button"],["/main/stations/footer","audioThemeborderColor","border"],["/main/stations/footer/label","audioThemetextColor","text"],["/main/timer/title","audioThemetextColor","text"],["/main/timer/back","bg","button"],["/main/timer/back","audioThemeborderColor","border"],["/main/timer/back/label","audioThemetextColor","text"],["/main/timer/sub","audioThemetextColor","text"],["/main/timer/moon","audioThemetextColor","text"],["/main/timer/choice0","bg","button"],["/main/timer/choice0","audioThemeborderColor","border"],["/main/timer/choice0/label","audioThemetextColor","text"],["/main/timer/choice1","bg","button"],["/main/timer/choice1","audioThemeborderColor","border"],["/main/timer/choice1/label","audioThemetextColor","text"],["/main/timer/choice2","bg","button"],["/main/timer/choice2","audioThemeborderColor","border"],["/main/timer/choice2/label","audioThemetextColor","text"],["/main/timer/choice3","bg","button"],["/main/timer/choice3","audioThemeborderColor","border"],["/main/timer/choice3/label","audioThemetextColor","text"],["/main/timer/note","audioThemetextColor","text"],["/main/timer/confirm","bg","button"],["/main/timer/confirm","audioThemeborderColor","border"],["/main/timer/confirm/label","audioThemetextColor","text"]];
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
function call(h,n,p){const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(p||{})));if(!r.success)throw Error(r.error||r.error_message||n);return r.data;}
function text(path,value){value=String(value);if(hidden||cache[path]===value)return;call(gui,'SetText',{Path:'/main/'+path,Text:value});cache[path]=value;}
function bind(path,key,value){if(key==='bg')value=audioThemeColor(value);value=String(value);const k=path+':'+key;if(hidden||cache[k]===value)return;call(gui,'SetBinding',{Path:'/main/'+path,Key:key,Value:value});cache[k]=value;}
function save(){try{call(storage,'FSWriteText',{Path:'/littlefs/radio-settings.json',Data:JSON.stringify({station:stations[current].id,favorites:favorites})});}catch(_){text('player/status','设置保存失败');}}
function show(next){screen=next;for(const p of ['player','stations','timer'])bind(p,'hidden',p!==next);if(next==='stations')renderList();if(next==='timer'){draft=minutes;renderTimer();}}
function renderPlayer(){const s=stations[current];text('player/title',s.display_name||s.name);text('player/meta',s.sub);text('player/toggle/label',state.active&&!state.paused?'暂停':'播放');text('player/timer/label',state.sleep_active?Math.ceil(state.sleep_remaining_seconds/60)+'分钟':'定时');}
function renderList(){
 const filtered=stations.map((s,i)=>({s:s,i:i})).filter(r=>category==='收藏'?favorites.includes(r.s.id):r.s.group===category);
 const pages=Math.max(1,Math.ceil(filtered.length/3));page=Math.min(page,pages-1);rows=filtered.slice(page*3,page*3+3);
 for(let i=0;i<4;i++)bind('stations/cat'+i,'bg',categories[i]===category?'#e5ad70':'#f4e7d4');
 for(let i=0;i<3;i++){bind('stations/row'+i,'hidden',!rows[i]);if(rows[i]){const r=rows[i];text('stations/row'+i+'/name',r.s.display_name||r.s.name);text('stations/row'+i+'/sub',r.s.sub);text('stations/row'+i+'/symbol',r.s.symbol);bind('stations/row'+i,'bg',r.i===current?'#ffedcf':'#fffaf1');}}
 text('stations/footer/label',!filtered.length?'还没有收藏的频道':pages>1?'下一页 '+(page+1)+'/'+pages:'中文优先 · 英语已标注');
}
function renderTimer(){for(let i=0;i<timerOptions.length;i++)bind('timer/choice'+i,'bg',timerOptions[i]===draft?'#ffebc7':'#fffaf1');text('timer/note',draft?draft+'分钟后停止播放':'持续收听，不自动停止');}
function play(index){current=index;state={};renderPlayer();text('player/status','连接电台…');call(audio,'Play',{Station:stations[index].id});if(minutes)call(audio,'SetSleepTimer',{Minutes:minutes});save();show('player');poll();}
function move(step){const group=stations[current].group;const list=stations.map((s,i)=>i).filter(i=>category==='收藏'?favorites.includes(stations[i].id):stations[i].group===group);if(!list.length)return;let at=list.indexOf(current);if(at<0)at=step>0?-1:0;play(list[(at+step+list.length)%list.length]);}
function poll(){
 state=call(audio,'GetState');const at=stations.findIndex(s=>s.id===state.station);if(at>=0)current=at;
 const labels={Idle:'准备播放',Connecting:'连接电台…',Buffering:'缓冲中…',Playing:'正在播放',Paused:'已暂停',Reconnecting:'连接中断，正在重连…',TimerEnded:'定时结束，已停止',Error:'播放失败'};
 text('player/status',state.error?'播放失败，请切换频道或重试':(labels[state.state]||state.state));
 const mode=call(modes,'GetState');applyAudioTheme(mode);text('player/volume','音量 '+mode.resume_volume+'%'+(mode.do_not_disturb?' · 静音':''));
 try{const net=call(wifi,'GetGeneralState');text('player/connection',net==='Connected'?'Wi-Fi 已连接':'等待 Wi-Fi');}catch(_){}
 if(!state.sleep_active&&(state.state==='TimerEnded'||state.state==='Idle'))minutes=0;
 renderPlayer();
}
function action(name){
 if(name==='stations'){page=0;show('stations');return;}if(name==='back'||name==='timerBack'){show('player');return;}if(name==='timer'){show('timer');return;}
 if(name.indexOf('cat')===0){category=categories[Number(name.slice(3))];page=0;renderList();return;}
 if(name.indexOf('row')===0){const r=rows[Number(name.slice(3))];if(r)play(r.i);return;}
 if(name.indexOf('choice')===0){draft=timerOptions[Number(name.slice(6))];renderTimer();return;}
 if(name==='timerConfirm'){call(audio,'SetSleepTimer',{Minutes:draft});minutes=draft;show('player');poll();return;}
 if(name==='listNext'){page++;const n=(category==='收藏'?favorites.length:stations.filter(s=>s.group===category).length);if(page*3>=n)page=0;renderList();return;}
 if(name==='lockScreen'){call(modes,'LockScreen');return;}
 if(name==='previous'){move(-1);return;}if(name==='next'){move(1);return;}
 if(name==='toggle'){state=call(audio,'GetState');if(state.active){call(audio,state.paused?'Resume':'Pause');poll();}else play(current);}
}
globalThis.brookesia_app={
 on_start(){gui=brookesia.start_service('SystemGui');storage=brookesia.start_service('Storage');audio=brookesia.start_service('Radio');volume=brookesia.start_service('AudioPlayback');modes=brookesia.start_service('DeviceModes');wifi=brookesia.start_service('Wifi');timer=brookesia.start_service('SystemTimer');
  try{stations=JSON.parse(call(storage,'FSReadText',{Path:'/littlefs/apps/local.radio/app/catalog.json'}));}catch(_){stations=JSON.parse(call(storage,'FSReadText',{Path:'/sdcard/apps/local.radio/app/catalog.json'}));}
  try{const saved=JSON.parse(call(storage,'FSReadText',{Path:'/littlefs/radio-settings.json'}));favorites=Array.isArray(saved.favorites)?saved.favorites.filter(id=>stations.some(s=>s.id===id)):[];const at=stations.findIndex(s=>s.id===saved.station);if(at>=0)current=at;}catch(_){}
  const actions=['stations','back','timerBack','timer','timerConfirm','listNext','lockScreen','previous','next','toggle','cat0','cat1','cat2','cat3','row0','row1','row2','choice0','choice1','choice2','choice3'];
  for(const n of actions)call(gui,'SubscribeAction',{Action:n});hidden=false;cache={};show('player');poll();call(timer,'StartPeriodic',{Name:'radio',IntervalMs:1000});return true;},
 on_action(name){try{action(name);}catch(e){text('player/status',String(e));if(screen!=='player')text('timer/note',String(e));}return true;},
 on_timer(){if(!hidden)try{poll();}catch(e){text('player/status',String(e));}return true;},
 on_pause(){hidden=true;return true;},
 on_resume(){hidden=false;cache={};show(screen);poll();return true;},
 on_stop(){try{call(audio,'Stop');}catch(_){}return true;}
};
})();
