(function () {
'use strict';
let gui, audio, storage, timer, tracks=[], index=0, current=null, playing=null, hidden=false, cache={}, volume=20, bookmark=null, lastSaved=0;
function call(handle,name,args){const r=JSON.parse(brookesia.call_function(handle,name,JSON.stringify(args||{})));if(!r.success)throw new Error(r.error||r.error_message||name);return r.data;}
function text(id,value){value=String(value);if(cache[id]===value||hidden)return;call(gui,'SetText',{Path:'/main/'+id,Text:value});cache[id]=value;}
function clock(seconds){seconds=Math.max(0,Math.floor(Number(seconds)||0));return Math.floor(seconds/3600)+':'+String(Math.floor(seconds%3600/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');}
function save(){if(!playing||!playing.path||playing.path==='@tone')return;bookmark={path:playing.path,position:playing.position||0};call(storage,'FSWriteText',{Path:'/littlefs/audiobook-bookmark.json',Data:JSON.stringify(bookmark)});lastSaved=Date.now();}
function refresh(){
  const result=call(audio,'List');tracks=Array.isArray(result.tracks)?result.tracks:[];
  if(tracks.length){const at=bookmark?tracks.findIndex(t=>t.path===bookmark.path):-1;index=at>=0?at:Math.min(index,tracks.length-1);current=tracks[index];text('chapter',current.title);text('status','共 '+tracks.length+' 章 · 点击播放');}
  else {current=null;text('chapter','装卡后扫描章节');text('status',result.mounted?'请将 MP3/WAV 放入 audiobooks 文件夹':'未检测到 SD 卡 · 装卡后重启');}
}
function play(){
  if(!current){text('status','请先装卡并扫描章节');return;}
  const position=bookmark&&bookmark.path===current.path?bookmark.position:0;
  call(audio,'Play',{Path:current.path,Position:position});text('chapter',current.title);poll();
}
function move(delta){if(!tracks.length)return;save();index=Math.max(0,Math.min(tracks.length-1,index+delta));current=tracks[index];bookmark={path:current.path,position:0};play();}
function poll(){
  const next=call(audio,'GetState');
  if(playing&&playing.state!=='Ended'&&next.state==='Ended'&&next.path!=='@tone'){
    playing=next;bookmark={path:next.path,position:0};save();
    if(index+1<tracks.length){index++;current=tracks[index];bookmark={path:current.path,position:0};play();return;}
  }
  playing=next;
  if(next.path==='@tone'&&next.active)text('status','正在播放测试音');
  else if(next.state==='Error')text('status','播放失败：'+next.error);
  else if(next.active)text('status',next.state==='Paused'?'已暂停':'扬声器播放中');
  else if(next.state==='Ended')text('status',next.path==='@tone'?'测试音播放结束':'本章播放结束');
  text('progress',clock(next.position)+(next.duration?' / '+clock(next.duration):''));
  text('transport/toggle/label',next.active&&next.state!=='Paused'?'暂停':'播放');
  if(next.active&&next.path!=='@tone'&&Date.now()-lastSaved>15000)save();
}
function action(name){
  if(name==='scan')refresh();
  else if(name==='test'){save();call(audio,'TestTone');poll();}
  else if(name==='previous')move(-1);
  else if(name==='next')move(1);
  else if(name==='toggle'){
    if(playing&&playing.active){call(audio,playing.state==='Paused'?'Resume':'Pause');poll();save();}
    else play();
  }else if(name==='back'||name==='forward'){
    if(playing&&playing.active&&playing.path!=='@tone')call(audio,'Seek',{Seconds:Math.max(0,playing.position+(name==='back'?-30:30))});
  }else if(name==='quieter'||name==='louder'){
    const playback=brookesia.start_service('AudioPlayback');volume=Math.max(0,Math.min(100,volume+(name==='quieter'?-5:5)));call(playback,'SetVolume',{Volume:volume});volume=call(playback,'GetVolume');text('volume','音量 '+volume+'%');
  }
}
globalThis.brookesia_app={
  on_start(){gui=brookesia.start_service('SystemGui');audio=brookesia.start_service('Audiobook');storage=brookesia.start_service('Storage');timer=brookesia.start_service('SystemTimer');
    for(const name of ['scan','test','previous','next','toggle','back','forward','quieter','louder'])call(gui,'SubscribeAction',{Action:name});
    try{bookmark=JSON.parse(call(storage,'FSReadText',{Path:'/littlefs/audiobook-bookmark.json'}));}catch(_){}
    try{volume=call(brookesia.start_service('AudioPlayback'),'GetVolume');}catch(_){}
    hidden=false;text('volume','音量 '+volume+'%');refresh();poll();call(timer,'StartPeriodic',{Name:'audiobook',IntervalMs:1000});return true;},
  on_timer(){if(!hidden)try{poll();}catch(e){text('status',String(e));}return true;},
  on_action(name){try{action(name);}catch(e){text('status',String(e));}return true;},
  on_pause(){try{save();}catch(_){}hidden=true;return true;},
  on_resume(){hidden=false;cache={};if(current)text('chapter',current.title);text('volume','音量 '+volume+'%');poll();return true;},
  on_stop(){try{save();call(audio,'Stop');}catch(_){}return true;}
};
})();
