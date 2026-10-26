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
let gui, audio, storage, modes, timer, playback, localVoice, tracks=[], index=0, current=null, playing=null, hidden=false, cache={}, volume=20, bookmark=null, lastSaved=0;
function call(handle,name,args){const r=JSON.parse(brookesia.call_function(handle,name,JSON.stringify(args||{})));if(!r.success)throw new Error(r.error||r.error_message||name);return r.data;}
function text(id,value){value=String(value);if(cache[id]===value||hidden)return;call(gui,'SetText',{Path:'/main/'+id,Text:value});cache[id]=value;}
function clock(seconds){seconds=Math.max(0,Math.floor(Number(seconds)||0));return Math.floor(seconds/3600)+':'+String(Math.floor(seconds%3600/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');}
function save(){if(!playing||!playing.path||playing.path==='@tone')return;bookmark={path:playing.path,position:playing.position||0};call(storage,'FSWriteText',{Path:'/littlefs/audiobook-bookmark.json',Data:JSON.stringify(bookmark)});lastSaved=Date.now();}
function refresh(){
  const result=call(audio,'List');tracks=Array.isArray(result.tracks)?result.tracks:[];
  if(tracks.length){const at=bookmark?tracks.findIndex(t=>t.path===bookmark.path):-1;index=at>=0?at:Math.min(index,tracks.length-1);current=tracks[index];text('chapter',title(current));text('status','共 '+tracks.length+' 章 · 点击播放');}
  else {current=null;text('chapter','装卡后扫描章节');text('status',result.mounted?'请将 MP3/WAV 放入 audiobooks 文件夹':'未检测到 SD 卡 · 装卡后重启');}
}
function title(track){
  const file=track.path.slice(track.path.lastIndexOf('/')+1);
  return storyTitles[file]||file.replace(/\.(mp3|wav)$/i,'');
}
function play(){
  if(!current){text('status','请先装卡并扫描章节');return;}
  const position=bookmark&&bookmark.path===current.path?bookmark.position:0;
  call(audio,'Play',{Path:current.path,Position:position});text('chapter',title(current));poll();
}
function move(delta){if(!tracks.length)return;save();index=Math.max(0,Math.min(tracks.length-1,index+delta));current=tracks[index];bookmark={path:current.path,position:0};play();}
function poll(){
  const next=call(audio,'GetState');
  const actual=tracks.findIndex(t=>t.path===next.path);
  if(actual>=0&&(!current||current.path!==next.path)){index=actual;current=tracks[index];text('chapter',title(current));}
  if(playing&&playing.state!=='Ended'&&next.state==='Ended'&&next.path!=='@tone'){
    const sleepJustEnded=next.state==='SleepEnded'&&(!playing||playing.state!=='SleepEnded');
  playing=next;bookmark={path:next.path,position:0};save();
    if(index+1<tracks.length){index++;current=tracks[index];bookmark={path:current.path,position:0};play();return;}
  }
  const sleepJustEnded=next.state==='SleepEnded'&&(!playing||playing.state!=='SleepEnded');
  playing=next;
  if(next.path==='@tone'&&next.active)text('status','正在播放测试音');
  else if(next.state==='Error')text('status','播放失败：'+next.error);
  else if(next.active)text('status',next.state==='Goodnight'?'晚安，做个好梦':next.state==='Paused'?'已暂停':'扬声器播放中');
  else if(next.state==='SleepEnded')text('status','故事已停 · 晚安');
  else if(next.state==='Ended')text('status',next.path==='@tone'?'测试音播放结束':'本章播放结束');
  const remaining=Math.max(0,Number(next.sleep_remaining_seconds)||0);
  text('sleepStatus',next.sleep_finishing?'晚安，做个好梦':next.sleep_active?(next.sleep_fading?'正在淡出 ':'睡眠定时 ')+String(Math.floor(remaining/60)).padStart(2,'0')+':'+String(remaining%60).padStart(2,'0'):next.sleep_completed?'定时结束 · 已停止':'睡眠定时 · 最后两分钟渐弱');
  try{const sound=call(modes,'GetState');volume=call(playback,'GetVolume');text('volume',sound.do_not_disturb?'音量 '+sound.resume_volume+'% · 勿扰静音':'音量 '+volume+'% · 两侧实体键调节');}catch(_){}
  try{const local=call(localVoice,'GetState');text('voice/label',local.listening?'我在听，请说命令':'点一下说话 · 离线');if(local.error)text('status','离线语音：'+local.error);}catch(_){}
  if(sleepJustEnded)save();
  text('progress',clock(next.position)+(next.duration?' / '+clock(next.duration):''));
  text('transport/toggle/label',next.active&&next.state!=='Paused'?'暂停':'播放');
  if(next.active&&next.path!=='@tone'&&Date.now()-lastSaved>15000)save();
}
function action(name){
  if(name==='offlineSpeak'){call(localVoice,'ListenNow');text('status','我在听，请说命令');return;}
  if(name==='sleep15'||name==='sleep30'||name==='sleep45'||name==='sleepOff'){call(audio,'SetSleepTimer',{Minutes:name==='sleepOff'?0:Number(name.slice(5))});poll();}
  else if(name==='previous')move(-1);
  else if(name==='next')move(1);
  else if(name==='toggle'){
    if(playing&&playing.active){call(audio,playing.state==='Paused'?'Resume':'Pause');poll();save();}
    else play();
  }else if(name==='back'||name==='forward'){
    if(playing&&playing.active&&playing.path!=='@tone')call(audio,'Seek',{Seconds:Math.max(0,playing.position+(name==='back'?-30:30))});
  }
}
globalThis.brookesia_app={
  on_start(){gui=brookesia.start_service('SystemGui');audio=brookesia.start_service('Audiobook');modes=brookesia.start_service('DeviceModes');storage=brookesia.start_service('Storage');timer=brookesia.start_service('SystemTimer');playback=brookesia.start_service('AudioPlayback');localVoice=brookesia.start_service('OfflineVoice');
    for(const name of ['previous','next','toggle','back','forward','sleep15','sleep30','sleep45','sleepOff','offlineSpeak'])call(gui,'SubscribeAction',{Action:name});
    try{bookmark=JSON.parse(call(storage,'FSReadText',{Path:'/littlefs/audiobook-bookmark.json'}));}catch(_){}
    try{volume=call(playback,'GetVolume');}catch(_){}
    hidden=false;text('volume','音量 '+volume+'% · 两侧实体键调节');refresh();poll();call(timer,'StartPeriodic',{Name:'audiobook',IntervalMs:1000});return true;},
  on_timer(){if(!hidden)try{poll();}catch(e){text('status',String(e));}return true;},
  on_action(name){try{action(name);}catch(e){text('status',String(e));}return true;},
  on_pause(){try{save();}catch(_){}hidden=true;return true;},
  on_resume(){hidden=false;cache={};refresh();text('volume','音量 '+volume+'% · 两侧实体键调节');poll();return true;},
  on_stop(){try{save();call(audio,'Stop');}catch(_){}return true;}
};
})();
