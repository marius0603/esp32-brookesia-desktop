(function(){'use strict';
const categories=['儿童','音乐','资讯','收藏'],timerOptions=[0,15,30,45];
let gui,storage,audio,volume,modes,wifi,timer,stations=[],current=0,category='儿童',favorites=[],minutes=0,draft=0,page=0,rows=[],hidden=false,screen='player',state={},cache={};
function call(h,n,p){const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(p||{})));if(!r.success)throw Error(r.error||r.error_message||n);return r.data;}
function text(path,value){value=String(value);if(hidden||cache[path]===value)return;call(gui,'SetText',{Path:'/main/'+path,Text:value});cache[path]=value;}
function bind(path,key,value){value=String(value);const k=path+':'+key;if(hidden||cache[k]===value)return;call(gui,'SetBinding',{Path:'/main/'+path,Key:key,Value:value});cache[k]=value;}
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
 const mode=call(modes,'GetState');text('player/volume','音量 '+mode.resume_volume+'%'+(mode.do_not_disturb?' · 静音':''));
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
