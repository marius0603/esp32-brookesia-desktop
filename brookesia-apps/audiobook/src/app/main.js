(function () {
'use strict';
const storyTitles={
  '01-xiaoma-yueliang.mp3':'小马和月亮灯',
  '02-gudong.mp3':'咕咚',
  '03-xiaokedou-zhao-mama.mp3':'小蝌蚪找妈妈',
  '04-wuya-heshui.mp3':'乌鸦喝水',
  '05-xiaohouzi-xiashan.mp3':'小猴子下山',
  '06-hujiahuwei.mp3':'狐假虎威',
  '07-zuojingguantian.mp3':'坐井观天',
  '08-xiaoma-guohe.mp3':'小马过河',
  '09-xuehaizi.mp3':'雪孩子',
  '10-wangyangbulao.mp3':'亡羊补牢'
};
const sleepMinutes=[0,15,30,45];
const speeds=[0.5,0.75,1,1.25,1.5,2];
let speed=1;
const playModes=['sequence','random','repeat_one'];
let playMode='sequence';
let gui, audio, storage, modes, timer, playback, localVoice, tracks=[], index=0, current=null, playing=null, hidden=false, cache={}, volume=20, bookmark=null, lastSaved=0,sleepSelected=-1;
// AUDIO_THEME_BEGIN
let audioThemeDark=false,audioThemeIndex=-1,audioThemeCore;
const audioThemeNodes=[["/main","audioThemebgColor","root"],["/main/header","audioThemebgColor","panel"],["/main/header","audioThemeborderColor","border"],["/main/header/volume","audioThemetextColor","text"],["/main/header/lock","audioThemebgColor","button"],["/main/header/lock","audioThemeborderColor","border"],["/main/header/lock/label","audioThemetextColor","text"],["/main/player","audioThemebgColor","panel"],["/main/player","audioThemeborderColor","border"],["/main/player","audioThemebgGradientColor","panel"],["/main/player/chapter","audioThemetextColor","text"],["/main/player/progress","audioThemetextColor","text"],["/main/player/status","audioThemetextColor","text"],["/main/transport/previous","audioThemebgColor","button"],["/main/transport/previous/label","audioThemetextColor","text"],["/main/transport/toggle","audioThemebgColor","button"],["/main/transport/toggle/label","audioThemetextColor","text"],["/main/transport/next","audioThemebgColor","button"],["/main/transport/next/label","audioThemetextColor","text"],["/main/sleep","audioThemebgColor","panel"],["/main/sleep","audioThemeborderColor","border"],["/main/sleep/label","audioThemetextColor","text"],["/main/sleep/choice","audioThemebgColor","button"],["/main/sleep/choice","audioThemetextColor","text"],["/main/sleep/choice","audioThemeborderColor","border"],["/main/sleep/sleepStatus","audioThemetextColor","text"],["/main/tools","audioThemebgColor","panel"],["/main/tools","audioThemeborderColor","border"],["/main/tools/voice","audioThemebgColor","button"],["/main/tools/voice","audioThemeborderColor","border"],["/main/tools/voice/label","audioThemetextColor","text"],["/main/tools/speed","audioThemebgColor","button"],["/main/tools/speed","audioThemeborderColor","border"],["/main/tools/speed/label","audioThemetextColor","text"],["/main/tools/mode","audioThemebgColor","button"],["/main/tools/mode","audioThemeborderColor","border"]];
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
function call(handle,name,args){const r=JSON.parse(brookesia.call_function(handle,name,JSON.stringify(args||{})));if(!r.success)throw new Error(r.error||r.error_message||name);return r.data;}
const textPaths={volume:'header/volume',chapter:'player/chapter',progress:'player/progress',status:'player/status',sleepStatus:'sleep/sleepStatus'};
function text(id,value){value=String(value);if(cache[id]===value||hidden)return;call(gui,'SetText',{Path:'/main/'+(textPaths[id]||id),Text:value});cache[id]=value;}
function clock(seconds){seconds=Math.max(0,Math.floor(Number(seconds)||0));return Math.floor(seconds/3600)+':'+String(Math.floor(seconds%3600/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');}
function save(){if(!playing||!playing.path||playing.path==='@tone')return;bookmark={path:playing.path,position:playing.state==='Ended'?0:playing.position||0};call(storage,'FSWriteText',{Path:'/littlefs/audiobook-bookmark.json',Data:JSON.stringify(bookmark)});lastSaved=Date.now();}
function syncMode(){if(hidden||cache.mode===playMode)return;call(gui,'SetViewSrc',{Path:'/main/tools/mode/icon',Src:'mode_'+playMode});cache.mode=playMode;}
function randomIndex(){if(tracks.length<2)return index;const at=Math.floor(Math.random()*(tracks.length-1));return at>=index?at+1:at;}
function startAt(at){index=at;current=tracks[index];bookmark={path:current.path,position:0};play();}
function refresh(){
  const result=call(audio,'List');tracks=Array.isArray(result.tracks)?result.tracks:[];
  if(tracks.length){const at=bookmark?tracks.findIndex(t=>t.path===bookmark.path):-1;index=at>=0?at:Math.min(index,tracks.length-1);current=tracks[index];text('chapter',title(current));text('status','第 '+(index+1)+' / '+tracks.length+' 章');}
  else {current=null;text('chapter','暂无故事');text('status',result.mounted?'没有可播放的故事':'未检测到 SD 卡');}
}
function title(track){
  const file=track.path.slice(track.path.lastIndexOf('/')+1);
  return storyTitles[file]||file.replace(/\.(mp3|wav)$/i,'');
}
function play(){
  if(!current){text('status','暂无可播放故事');return;}
  const position=bookmark&&bookmark.path===current.path?bookmark.position:0;
  call(audio,'Play',{Path:current.path,Position:position});text('chapter',title(current));poll();
}
function move(delta){if(!tracks.length)return;save();startAt(playMode==='random'?randomIndex():Math.max(0,Math.min(tracks.length-1,index+delta)));}
function syncSleep(next){
  const selected=next.sleep_active?Math.max(0,sleepMinutes.indexOf(next.sleep_minutes)):0;
  if(selected===sleepSelected)return;
  call(gui,'SetBinding',{Path:'/main/sleep/choice',Key:'selected',Value:String(selected)});sleepSelected=selected;
}
function poll(){
  const next=call(audio,'GetState');
  if(playModes.includes(next.play_mode))playMode=next.play_mode;
  syncMode();
  speed=speeds.includes(next.speed)?next.speed:1;text('tools/speed/label',speed+'x');
  syncSleep(next);
  const actual=tracks.findIndex(t=>t.path===next.path);
  if(actual>=0&&(!current||current.path!==next.path)){index=actual;current=tracks[index];text('chapter',title(current));}
  if(playing&&playing.state!=='Ended'&&next.state==='Ended'&&actual>=0){
    playing=next;bookmark={path:next.path,position:0};save();
    if(playMode==='repeat_one'){startAt(index);return;}
    if(playMode==='random'){startAt(randomIndex());return;}
    if(index+1<tracks.length){startAt(index+1);return;}
  }
  const sleepJustEnded=next.state==='SleepEnded'&&(!playing||playing.state!=='SleepEnded');
  playing=next;
  if(next.path==='@tone'&&next.active)text('status','正在播放测试音');
  else if(next.state==='Error')text('status','播放失败：'+next.error);
  else if(next.active)text('status',next.state==='Goodnight'?'晚安':next.state==='Paused'?'已暂停':'播放中');
  else if(next.state==='SleepEnded')text('status','已停止');
  else if(next.state==='Ended')text('status',next.path==='@tone'?'测试音播放结束':'本章播放结束');
  const remaining=Math.max(0,Number(next.sleep_remaining_seconds)||0);
  text('sleepStatus',next.sleep_finishing?'晚安':next.sleep_active?String(Math.floor(remaining/60)).padStart(2,'0')+':'+String(remaining%60).padStart(2,'0'):next.sleep_completed?'已结束':'');
  try{const sound=call(modes,'GetState');applyAudioTheme(sound);volume=call(playback,'GetVolume');text('volume',sound.do_not_disturb?'音量 '+sound.resume_volume+'% · 静音':'音量 '+volume+'%');}catch(_){}
  try{const local=call(localVoice,'GetState');text('tools/voice/label',local.listening?'正在听':'语音控制');if(local.error)text('status','离线语音：'+local.error);}catch(_){}
  if(sleepJustEnded&&actual>=0)save();
  text('progress',clock(next.position)+(next.duration?' / '+clock(next.duration):''));
  text('transport/toggle/label',next.active&&next.state!=='Paused'?'暂停':'播放');
  if(next.active&&next.path!=='@tone'&&Date.now()-lastSaved>15000)save();
}
function action(name){
  if(name==='speed'){call(audio,'SetSpeed',{Speed:speeds[(speeds.indexOf(speed)+1)%speeds.length]});poll();return;}
  if(name==='playMode'){
    const shared=call(audio,'GetState');if(playModes.includes(shared.play_mode))playMode=shared.play_mode;
    const selected=playModes[(playModes.indexOf(playMode)+1)%playModes.length];
    call(audio,'SetPlayMode',{Mode:selected});playMode=selected;syncMode();return;
  }
  if(name==='offlineSpeak'){call(localVoice,'ListenNow');text('status','正在听');return;}
  if(name==='lockScreen'){save();call(modes,'LockScreen');return;}
  if(name==='sleepChoice'){
    const value=call(gui,'GetBinding',{Path:'/main/sleep/choice',Key:'selected'});
    if(typeof value!=='string'||!/^\d+$/.test(value))return;
    const selected=Number(value);if(!Number.isInteger(selected)||selected<0||selected>=sleepMinutes.length)return;
    call(audio,'SetSleepTimer',{Minutes:sleepMinutes[selected]});sleepSelected=selected;poll();
  }
  else if(name==='previous')move(-1);
  else if(name==='next')move(1);
  else if(name==='toggle'){
    if(playing&&playing.active){call(audio,playing.state==='Paused'?'Resume':'Pause');poll();save();}
    else play();
  }
}
globalThis.brookesia_app={
  on_start(){gui=brookesia.start_service('SystemGui');audio=brookesia.start_service('Audiobook');modes=brookesia.start_service('DeviceModes');storage=brookesia.start_service('Storage');timer=brookesia.start_service('SystemTimer');playback=brookesia.start_service('AudioPlayback');localVoice=brookesia.start_service('OfflineVoice');
    for(const name of ['previous','next','toggle','sleepChoice','offlineSpeak','lockScreen','playMode','speed'])call(gui,'SubscribeAction',{Action:name});
    try{const saved=JSON.parse(call(storage,'FSReadText',{Path:'/littlefs/audiobook-play-mode.json'}));if(saved&&playModes.includes(saved.mode))playMode=saved.mode;}catch(_){}
    call(audio,'SetPlayMode',{Mode:playMode});
    try{bookmark=JSON.parse(call(storage,'FSReadText',{Path:'/littlefs/audiobook-bookmark.json'}));}catch(_){}
    try{volume=call(playback,'GetVolume');}catch(_){}
    hidden=false;sleepSelected=-1;text('volume','音量 '+volume+'%');refresh();poll();call(timer,'StartPeriodic',{Name:'audiobook',IntervalMs:1000});return true;},
  on_timer(){if(!hidden)try{poll();}catch(e){text('status',String(e));}return true;},
  on_action(name){try{action(name);}catch(e){text('status',String(e));}return true;},
  on_pause(){try{save();}catch(_){}hidden=true;return true;},
  on_resume(){hidden=false;cache={};sleepSelected=-1;refresh();text('volume','音量 '+volume+'%');poll();return true;},
  on_stop(){try{save();call(audio,'Stop');}catch(_){}return true;}
};
})();
