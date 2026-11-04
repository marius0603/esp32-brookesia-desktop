(function(){'use strict';
const modes=['sequence','random','repeat_one'],modeLabels=['顺序播放','随机播放','单曲循环'],minutes=[0,15,30,45];
const location={kind:'AppData',relative_path:'player.json'};
let gui,audio,core,device,timer,timerId,tracks=[],index=0,rows=[],page=0,view='player',hidden=false,cache={},state={},bookmark=null,mode='sequence',lastSaved=0,draft=0;
function call(h,n,p){const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(p||{})));if(!r.success)throw Error(r.error||r.error_message||n);return r.data;}
function text(path,value){value=String(value);if(hidden||cache[path]===value)return;call(gui,'SetText',{Path:'/main/'+path,Text:value});cache[path]=value;}
function bind(path,key,value){value=String(value);const id=path+':'+key;if(hidden||cache[id]===value)return;call(gui,'SetBinding',{Path:'/main/'+path,Key:key,Value:value});cache[id]=value;}
function title(t){return t.title||t.path.slice(t.path.lastIndexOf('/')+1).replace(/\.(mp3|wav)$/i,'');}
function clock(t){t=Math.max(0,Math.floor(Number(t)||0));return Math.floor(t/60)+':'+String(t%60).padStart(2,'0');}
function own(s){return !!s.path&&s.path.startsWith('/sdcard/audiobooks/songs/');}
function save(){
 if(own(state))bookmark={path:state.path,position:state.state==='Ended'?0:state.position||0};
 call(core,'StorageWrite',{Location:location,Data:JSON.stringify({bookmark:bookmark,mode:mode})});lastSaved=Date.now();
}
function refresh(){
 const list=call(audio,'ListSongs');tracks=Array.isArray(list.tracks)?list.tracks:[];
 const at=bookmark?tracks.findIndex(t=>t.path===bookmark.path):-1;index=at>=0?at:Math.max(0,Math.min(index,tracks.length-1));
 if(!tracks.length)text('player/status',list.mounted?'暂无歌曲':'请插入 SD 卡');
 render();
}
function render(){
 text('player/title',tracks.length?title(tracks[index]):'儿歌');
 text('player/count',tracks.length?'第 '+(index+1)+' / '+tracks.length+' 首':'暂无歌曲');
 text('player/mode/label',modeLabels[modes.indexOf(mode)]);
}
function renderList(){
 const pages=Math.max(1,Math.ceil(tracks.length/4));page=Math.max(0,Math.min(page,pages-1));rows=tracks.slice(page*4,page*4+4);
 for(let i=0;i<4;i++){bind('songs/row'+i,'hidden',!rows[i]);text('songs/row'+i+'/label',rows[i]?(page*4+i+1)+'. '+title(rows[i]):'');}
 text('songs/page',(page+1)+' / '+pages);
}
function show(next){view=next;for(const n of ['player','songs','timer'])bind(n,'hidden',n!==next);if(next==='songs')renderList();}
function random(){if(tracks.length<2)return index;const n=Math.floor(Math.random()*(tracks.length-1));return n>=index?n+1:n;}
function play(at,resume){
 if(!tracks.length){refresh();return;}
 index=at;const t=tracks[index];const position=resume&&bookmark&&bookmark.path===t.path?bookmark.position||0:0;
 call(audio,'SetSpeed',{Speed:1});call(audio,'Play',{Path:t.path,Position:position});
 state=call(audio,'GetState');bookmark={path:t.path,position:position};save();show('player');render();poll();
}
function poll(){
 const next=call(audio,'GetState');
 const at=own(next)?tracks.findIndex(t=>t.path===next.path):-1;
 const ended=at>=0&&own(state)&&state.path===next.path&&state.state!=='Ended'&&next.state==='Ended';
 state=next;if(at>=0){index=at;render();}
 if(ended){
  save();if(mode==='repeat_one'){play(index,false);return;}
  if(mode==='random'){play(random(),false);return;}
  if(index+1<tracks.length){play(index+1,false);return;}
 }
 const active=own(state)&&state.active;
 if(tracks.length)text('player/status',own(state)&&state.error?'播放失败':active?(state.state==='Paused'?'已暂停':state.state==='Goodnight'?'晚安':'播放中'):own(state)&&state.state==='SleepEnded'?'定时结束':own(state)&&state.state==='Ended'?'歌曲结束':'准备播放');
 text('player/progress',own(state)?clock(state.position)+' / '+clock(state.duration):'0:00 / 0:00');
 text('player/toggle/label',active&&state.state!=='Paused'?'暂停':'播放');
 const d=call(device,'GetState');text('header/volume','音量 '+d.resume_volume+'%'+(d.do_not_disturb?' · 静音':''));
 text('player/sleep',state.sleep_active?clock(state.sleep_remaining_seconds):'');
 if(active&&Date.now()-lastSaved>=15000)save();
}
function action(n){
 if(n==='toggle'){state=call(audio,'GetState');if(own(state)&&state.active){call(audio,state.state==='Paused'?'Resume':'Pause');poll();save();}else play(index,true);return;}
 if(n==='previous'||n==='next'){if(tracks.length){save();play(mode==='random'?random():(index+(n==='next'?1:tracks.length-1))%tracks.length,false);}return;}
 if(n==='mode'){mode=modes[(modes.indexOf(mode)+1)%modes.length];save();render();return;}
 if(n==='songs'){page=Math.floor(index/4);show('songs');return;}
 if(n==='back'||n==='timerBack'){show('player');return;}
 if(n==='listPrev'||n==='listNext'){page+=(n==='listNext'?1:-1);renderList();return;}
 if(/^row[0-3]$/.test(n)){const i=Number(n.slice(3));if(rows[i])play(page*4+i,false);return;}
 if(n==='sleep'){draft=state.sleep_active?Math.max(0,minutes.indexOf(state.sleep_minutes)):0;show('timer');renderTimer();return;}
 if(/^choice[0-3]$/.test(n)){draft=Number(n.slice(6));renderTimer();return;}
 if(n==='timerConfirm'){call(audio,'SetSleepTimer',{Minutes:minutes[draft]});show('player');poll();return;}
 if(n==='lock'){save();call(device,'LockScreen');}
}
function renderTimer(){for(let i=0;i<4;i++)bind('timer/choice'+i,'bg',draft===i?'#e8c477':'#fff6e2');}
globalThis.brookesia_app={
 on_start(){
  gui=brookesia.start_service('SystemGui');audio=brookesia.start_service('Audiobook');core=brookesia.start_service('SystemCore');device=brookesia.start_service('DeviceModes');timer=brookesia.start_service('SystemTimer');
  hidden=false;cache={};
  for(const n of ['toggle','previous','next','mode','songs','back','timerBack','listPrev','listNext','row0','row1','row2','row3','sleep','choice0','choice1','choice2','choice3','timerConfirm','lock'])call(gui,'SubscribeAction',{Action:n});
  try{const saved=JSON.parse(call(core,'StorageRead',{Location:location}));bookmark=saved.bookmark;if(modes.includes(saved.mode))mode=saved.mode;}catch(_){}
  state=call(audio,'GetState');refresh();show('player');poll();timerId=call(timer,'StartPeriodic',{Name:'nursery-songs',IntervalMs:1000});return true;
 },
 on_action(n){try{action(n);}catch(e){show('player');text('player/status',String(e.message||e));}return true;},
 on_timer(){if(!hidden)try{poll();}catch(e){text('player/status',String(e.message||e));}return true;},
 on_pause(){try{save();}catch(_){}hidden=true;return true;},
 on_resume(){hidden=false;cache={};refresh();show(view);poll();return true;},
 on_stop(){try{save();if(own(call(audio,'GetState')))call(audio,'Stop');}catch(_){}try{if(timerId)call(timer,'Stop',{TimerId:timerId});}catch(_){}hidden=true;return true;}
};
})();
