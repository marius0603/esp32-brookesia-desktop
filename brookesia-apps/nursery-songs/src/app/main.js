(function(){'use strict';
const modes=['sequence','random','repeat_one'],modeLabels=['顺序播放','随机播放','单曲循环'],minutes=[0,15,30,45];
const location={kind:'AppData',relative_path:'player.json'};
let gui,audio,core,device,timer,timerId,allTracks=[],collection='nursery',bookmarks={},tracks=[],index=0,rows=[],page=0,view='collections',hidden=false,cache={},state={},bookmark=null,mode='sequence',lastSaved=0,draft=0,startFresh=false;
// AUDIO_THEME_BEGIN
let audioThemeDark=false,audioThemeIndex=-1,audioThemeCore;
const audioThemeNodes=[["/main","audioThemebgColor","root"],["/main/header/volume","audioThemetextColor","text"],["/main/header/lock","bg","button"],["/main/header/lock","audioThemeborderColor","border"],["/main/header/lock/label","audioThemetextColor","text"],["/main/header/collections","bg","button"],["/main/header/collections","audioThemeborderColor","border"],["/main/header/collections/label","audioThemetextColor","text"],["/main/collections/title","audioThemetextColor","text"],["/main/collections/nursery","bg","button"],["/main/collections/nursery","audioThemeborderColor","border"],["/main/collections/nursery/label","audioThemetextColor","text"],["/main/collections/lullaby","bg","button"],["/main/collections/lullaby","audioThemeborderColor","border"],["/main/collections/lullaby/label","audioThemetextColor","text"],["/main/collections/sources","bg","button"],["/main/collections/sources","audioThemeborderColor","border"],["/main/collections/sources/label","audioThemetextColor","text"],["/main/player/title","audioThemetextColor","text"],["/main/player/count","audioThemetextColor","text"],["/main/player/progress","audioThemetextColor","text"],["/main/player/status","audioThemetextColor","text"],["/main/player/previous","bg","button"],["/main/player/previous","audioThemeborderColor","border"],["/main/player/previous/label","audioThemetextColor","text"],["/main/player/toggle","bg","button"],["/main/player/toggle","audioThemeborderColor","border"],["/main/player/toggle/label","audioThemetextColor","text"],["/main/player/next","bg","button"],["/main/player/next","audioThemeborderColor","border"],["/main/player/next/label","audioThemetextColor","text"],["/main/player/songs","bg","button"],["/main/player/songs","audioThemeborderColor","border"],["/main/player/songs/label","audioThemetextColor","text"],["/main/player/mode","bg","button"],["/main/player/mode","audioThemeborderColor","border"],["/main/player/mode/label","audioThemetextColor","text"],["/main/player/sleepButton","bg","button"],["/main/player/sleepButton","audioThemeborderColor","border"],["/main/player/sleepButton/label","audioThemetextColor","text"],["/main/player/sleep","audioThemetextColor","text"],["/main/songs/heading","audioThemetextColor","text"],["/main/songs/row0","bg","button"],["/main/songs/row0","audioThemeborderColor","border"],["/main/songs/row0/label","audioThemetextColor","text"],["/main/songs/row1","bg","button"],["/main/songs/row1","audioThemeborderColor","border"],["/main/songs/row1/label","audioThemetextColor","text"],["/main/songs/row2","bg","button"],["/main/songs/row2","audioThemeborderColor","border"],["/main/songs/row2/label","audioThemetextColor","text"],["/main/songs/row3","bg","button"],["/main/songs/row3","audioThemeborderColor","border"],["/main/songs/row3/label","audioThemetextColor","text"],["/main/songs/prevPage","bg","button"],["/main/songs/prevPage","audioThemeborderColor","border"],["/main/songs/prevPage/label","audioThemetextColor","text"],["/main/songs/page","audioThemetextColor","text"],["/main/songs/nextPage","bg","button"],["/main/songs/nextPage","audioThemeborderColor","border"],["/main/songs/nextPage/label","audioThemetextColor","text"],["/main/songs/back","bg","button"],["/main/songs/back","audioThemeborderColor","border"],["/main/songs/back/label","audioThemetextColor","text"],["/main/timer/heading","audioThemetextColor","text"],["/main/timer/choice0","bg","button"],["/main/timer/choice0","audioThemeborderColor","border"],["/main/timer/choice0/label","audioThemetextColor","text"],["/main/timer/choice1","bg","button"],["/main/timer/choice1","audioThemeborderColor","border"],["/main/timer/choice1/label","audioThemetextColor","text"],["/main/timer/choice2","bg","button"],["/main/timer/choice2","audioThemeborderColor","border"],["/main/timer/choice2/label","audioThemetextColor","text"],["/main/timer/choice3","bg","button"],["/main/timer/choice3","audioThemeborderColor","border"],["/main/timer/choice3/label","audioThemetextColor","text"],["/main/timer/note","audioThemetextColor","text"],["/main/timer/back","bg","button"],["/main/timer/back","audioThemeborderColor","border"],["/main/timer/back/label","audioThemetextColor","text"],["/main/timer/confirm","bg","button"],["/main/timer/confirm","audioThemeborderColor","border"],["/main/timer/confirm/label","audioThemetextColor","text"],["/main/credits/title","audioThemetextColor","text"],["/main/credits/artist","audioThemetextColor","text"],["/main/credits/site","audioThemetextColor","text"],["/main/credits/license","audioThemetextColor","text"],["/main/credits/changes","audioThemetextColor","text"],["/main/credits/nursery","audioThemetextColor","text"],["/main/credits/back","bg","button"],["/main/credits/back","audioThemeborderColor","border"],["/main/credits/back/label","audioThemetextColor","text"]];
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
function bind(path,key,value){if(key==='bg')value=audioThemeColor(value);value=String(value);const id=path+':'+key;if(hidden||cache[id]===value)return;call(gui,'SetBinding',{Path:'/main/'+path,Key:key,Value:value});cache[id]=value;}
function title(t){return t.title||t.path.slice(t.path.lastIndexOf('/')+1).replace(/\.(mp3|wav)$/i,'');}
function clock(t){t=Math.max(0,Math.floor(Number(t)||0));return Math.floor(t/60)+':'+String(t%60).padStart(2,'0');}
function own(s){return !!s.path&&s.path.startsWith('/sdcard/audiobooks/songs/');}
function section(path){return path.startsWith('/sdcard/audiobooks/songs/lullabies/')?'lullaby':'nursery';}
function sectionName(){return collection==='lullaby'?'摇篮曲':'快乐儿歌';}
function save(){
 if(own(state)&&(state.active||state.state==='Ended'||state.state==='SleepEnded'))bookmarks[section(state.path)]={path:state.path,position:state.state==='Ended'?0:state.position||0};
 bookmark=bookmarks[collection]||null;
 call(core,'StorageWrite',{Location:location,Data:JSON.stringify({bookmark:bookmark,bookmarks:bookmarks,collection:collection,mode:mode})});lastSaved=Date.now();
}
function selectTracks(){
 tracks=allTracks.filter(t=>section(t.path)===collection);bookmark=bookmarks[collection]||null;
 const at=bookmark?tracks.findIndex(t=>t.path===bookmark.path):-1;
 index=at>=0?at:Math.max(0,Math.min(index,tracks.length-1));
 render();
}
function selectCollection(next){
 state=call(audio,'GetState');save();
 if(next!==collection&&own(state)&&state.active){call(audio,'Stop');state=call(audio,'GetState');}
 collection=next;index=0;selectTracks();startFresh=true;save();show('player');poll();
}
function refresh(){
 const list=call(audio,'ListSongs');allTracks=Array.isArray(list.tracks)?list.tracks:[];
 selectTracks();
 text('collections/nursery/label','快乐儿歌 · '+allTracks.filter(t=>section(t.path)==='nursery').length+'首');
 text('collections/lullaby/label','摇篮曲 · '+allTracks.filter(t=>section(t.path)==='lullaby').length+'首');
 if(!tracks.length)text('player/status',list.mounted?'本专区暂无歌曲':'请插入 SD 卡');
}

function render(){
 text('player/title',tracks.length?title(tracks[index]):sectionName());
 text('player/count',tracks.length?sectionName()+' '+(index+1)+' / '+tracks.length+' 首':'暂无歌曲');
 text('player/mode/label',modeLabels[modes.indexOf(mode)]);
}
function renderList(){
 text('songs/heading',sectionName()+'列表');
 const pages=Math.max(1,Math.ceil(tracks.length/4));page=Math.max(0,Math.min(page,pages-1));rows=tracks.slice(page*4,page*4+4);
 for(let i=0;i<4;i++){bind('songs/row'+i,'hidden',!rows[i]);text('songs/row'+i+'/label',rows[i]?(page*4+i+1)+'. '+title(rows[i]):'');}
 text('songs/page',(page+1)+' / '+pages);
}
function show(next){view=next;for(const n of ['collections','player','songs','timer','credits'])bind(n,'hidden',n!==next);if(next==='songs')renderList();}
function random(){if(tracks.length<2)return index;const n=Math.floor(Math.random()*(tracks.length-1));return n>=index?n+1:n;}
function play(at,resume){
 if(!tracks.length){refresh();return;}
 startFresh=false;index=at;const t=tracks[index];const position=resume&&bookmark&&bookmark.path===t.path?bookmark.position||0:0;
 call(audio,'SetSpeed',{Speed:1});call(audio,'Play',{Path:t.path,Position:position});
 state=call(audio,'GetState');bookmark={path:t.path,position:position};save();show('player');render();poll();
}
function poll(){
 const next=call(audio,'GetState');
 if(modes.includes(next.song_play_mode)&&mode!==next.song_play_mode){mode=next.song_play_mode;render();}
 if(own(next)&&next.active&&section(next.path)!==collection){collection=section(next.path);selectTracks();}
 const at=own(next)?tracks.findIndex(t=>t.path===next.path):-1;
 const ended=at>=0&&own(state)&&state.path===next.path&&state.state!=='Ended'&&next.state==='Ended';
 state=next;if(at>=0&&next.active){index=at;render();}
 if(ended){
  save();if(mode==='repeat_one'){play(index,false);return;}
  if(mode==='random'){play(random(),false);return;}
  if(index+1<tracks.length){play(index+1,false);return;}
 }
 const active=own(state)&&state.active;
 if(tracks.length)text('player/status',own(state)&&state.error?'播放失败':active?(state.state==='Paused'?'已暂停':state.state==='Goodnight'?'晚安':'播放中'):own(state)&&state.state==='SleepEnded'?'定时结束':own(state)&&state.state==='Ended'?'歌曲结束':'准备播放');
 text('player/progress',own(state)?clock(state.position)+' / '+clock(state.duration):'0:00 / 0:00');
 text('player/toggle/label',active&&state.state!=='Paused'?'暂停':'播放');
 const d=call(device,'GetState');applyAudioTheme(d);text('header/volume','音量 '+d.resume_volume+'%'+(d.do_not_disturb?' · 静音':''));
 text('player/sleep',state.sleep_active?clock(state.sleep_remaining_seconds):'');
 if(active&&Date.now()-lastSaved>=15000)save();
}
function action(n){
 if(n==='nursery'||n==='lullaby'){selectCollection(n);return;}
 if(n==='collections'){save();refresh();show('collections');return;}
 if(n==='credits'){show('credits');return;}
 if(n==='creditsBack'){show('collections');return;}
 if(n==='toggle'){state=call(audio,'GetState');if(!startFresh&&tracks[index]&&state.path===tracks[index].path&&state.active){call(audio,state.state==='Paused'?'Resume':'Pause');poll();save();}else {const resume=!startFresh;startFresh=false;play(index,resume);}return;}
 if(n==='previous'||n==='next'){if(tracks.length){save();play(mode==='random'?random():(index+(n==='next'?1:tracks.length-1))%tracks.length,false);}return;}
 if(n==='mode'){const selected=modes[(modes.indexOf(mode)+1)%modes.length];call(audio,'SetSongMode',{Mode:selected});mode=selected;save();render();return;}
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
  for(const n of ['collections','nursery','lullaby','credits','creditsBack','toggle','previous','next','mode','songs','back','timerBack','listPrev','listNext','row0','row1','row2','row3','sleep','choice0','choice1','choice2','choice3','timerConfirm','lock'])call(gui,'SubscribeAction',{Action:n});
  try{const saved=JSON.parse(call(core,'StorageRead',{Location:location}));bookmarks=saved.bookmarks||{};if(saved.bookmark&&!bookmarks[section(saved.bookmark.path)])bookmarks[section(saved.bookmark.path)]=saved.bookmark;if(saved.collection==='nursery'||saved.collection==='lullaby')collection=saved.collection;if(modes.includes(saved.mode))mode=saved.mode;}catch(_){}
  state=call(audio,'GetState');refresh();show('collections');poll();timerId=call(timer,'StartPeriodic',{Name:'nursery-songs',IntervalMs:1000});return true;
 },
 on_action(n){try{action(n);}catch(e){show('player');text('player/status',String(e.message||e));}return true;},
 on_timer(){if(!hidden)try{poll();}catch(e){text('player/status',String(e.message||e));}return true;},
 on_pause(){try{save();}catch(_){}hidden=true;return true;},
 on_resume(){hidden=false;cache={};refresh();show(view);poll();return true;},
 on_stop(){try{save();if(own(call(audio,'GetState')))call(audio,'Stop');}catch(_){}try{if(timerId)call(timer,'Stop',{TimerId:timerId});}catch(_){}hidden=true;return true;}
};
})();
