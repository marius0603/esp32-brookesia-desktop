(function(){
'use strict';
let gui,modes,timer,core,audio,playback,period=0,paused=false,cache={},voice=true,lastPrompt='',lastStage=-1,lastSpeech=0,lastTurn=-1,lastDistance=-1;
const turns=['继续直行','向左转','向右转','向左前方','向右前方','前方掉头','到达终点','按手机提示'];
function call(h,n,args){const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(args||{})));if(!r.success)throw new Error(r.error||n);return r.data;}
function text(id,value){value=String(value);if(cache[id]===value)return;call(gui,'SetText',{Path:'/main/'+id,Text:value});cache[id]=value;}
function bind(id,key,value){const k=id+':'+key;value=String(value);if(cache[k]===value)return;call(gui,'SetBinding',{Path:id?'/main/'+id:'/main',Key:key,Value:value});cache[k]=value;}
function meters(n){return typeof n!=='number'||n<0?'--':n>=1000?(n/1000).toFixed(1)+' 公里':Math.round(n)+' 米';}
function theme(){
 let dark=true;try{dark=call(core,'GetEnvironment').theme_id==='dark';}catch(_){}
 bind('','background',dark?'#090e17':'#f5eddf');
 for(const id of ['brand','distance','road'])bind(id,'ink',dark?'#edf2f8':'#453b31');
 for(const id of ['source','status','details','note','volume'])bind(id,'ink',dark?'#a6b4c7':'#7d6b58');
 for(const id of ['bluetooth/stem','bluetooth/top','bluetooth/middle','bluetooth/bottom','speaker/body','speaker/cone','speaker/wave','battery/fill','minus/h','plus/h','plus/v'])bind(id,'foreground',dark?'#72e1c4':'#1b8f7c');
 for(const id of ['minus','plus'])bind(id,'background',dark?'#162431':'#fffaf1');
 bind('turn','ink',dark?'#71ddc9':'#197e70');
 bind('divider','background',dark?'#2a3648':'#dfd0b7');
 bind('replay','background',dark?'#172a28':'#e1eddb');bind('replay/label','ink',dark?'#71ddc9':'#197e70');
 bind('voice','background',dark?'#172a28':'#e1eddb');bind('voice/label','ink',dark?'#71ddc9':'#197e70');
}
function stopSpeech(){try{call(audio,'StopNavigationPrompt');}catch(_){} }
function speak(s,t,force){
 if(!voice&&!force)return;
 if(t===7&&!force){stopSpeech();return;}
 // Notification prose changes with every distance update: it is not a road ID.
 const key=s.source+'|'+t+(s.source===2?'':'|'+s.road);
 if(lastTurn!==-1&&lastTurn!==t){stopSpeech();lastPrompt='';lastStage=-1;lastSpeech=0;}
 if(key===lastPrompt&&lastDistance>=0&&lastDistance<=100&&s.distance>=200){lastPrompt='';lastStage=-1;}
 lastTurn=t;lastDistance=s.distance;
 const stage=t>=6||s.distance<0?0:s.distance<=30?2:s.distance<=100?1:0;
 if(!force&&(key===lastPrompt&&stage<=lastStage||lastSpeech&&Date.now()-lastSpeech<8000))return;
 try{
  const mode=call(modes,'GetState');if(mode.do_not_disturb||mode.resume_volume===0)return;
  call(audio,'PlayNavigationPrompt',{Turn:t,Stage:stage});lastPrompt=key;lastStage=stage;lastSpeech=Date.now();
 }catch(_){} // A busy codec is left alone; no interruption or unbounded queue.
}
function render(s){
 const fresh=!!s.received&&!s.stale&&s.phase!==2;
 text('source',s.received?(['离线演示','高德模拟','高德通知'][s.source]||'手机同步'):'手机蓝牙同步');
 text('status',!s.received?'等待手机连接':s.phase===2?'导航已停止':s.stale?'数据已过期':'蓝牙同步中');
 bind('arrow','hidden',!fresh);bind('status','hidden',fresh);
 if(!fresh){stopSpeech();text('distance','--');text('turn',s.stale&&s.received?'请查看手机':'等待导航');text('road','在小马遥控中开启导航同步');text('details','不使用设备定位，不独立算路');return;}
 const t=Number.isInteger(s.turn)&&s.turn>=0&&s.turn<8?s.turn:7;
 if(cache.arrow!==t){call(gui,'SetViewSrc',{Path:'/main/arrow',Src:'turn_'+t});cache.arrow=t;}
 text('distance',s.phase===1||t===6?'已到达':meters(s.distance));
 bind('distance','size',s.distance>=1000?48:72);
 text('turn',turns[t]);let words=String(s.road||'按手机提示');const entered=words.indexOf('进入');if(entered>=0)words=words.slice(entered);words=words.split(/[｜|·\r\n]/)[0].replace(/[\uE000-\uF8FF\u200B-\u200F\u202A-\u202E\uFE00-\uFE0F\uFFFD]/g,'').replace(/[，,；;。\s]+$/g,'');let end=Math.min(16,words.length);if(end<words.length&&words.charCodeAt(end-1)>=0xd800&&words.charCodeAt(end-1)<=0xdbff)--end;text('road',words.slice(0,end)+(words.length>end?'…':''));
 text('details','剩余 '+meters(s.remaining)+'  ·  '+(s.seconds<0?'--':Math.max(1,Math.ceil(s.seconds/60)))+' 分钟');
 speak(s,t);
}
function tick(){if(paused)return;try{const m=call(modes,'GetState');text('volume',m.resume_volume+'%'+(m.do_not_disturb?' · 静音':''));const battery=m.battery_status&255;bind('battery/fill','width',battery<=100?Math.max(1,Math.round(21*battery/100)):1); }catch(_){}try{render(call(modes,'GetNavigationState'));}catch(_){render({});text('status','服务暂不可用');}}
globalThis.brookesia_app={
 on_start(){gui=brookesia.start_service('SystemGui');modes=brookesia.start_service('DeviceModes');timer=brookesia.start_service('SystemTimer');core=brookesia.start_service('SystemCore');audio=brookesia.start_service('LearningAudio');playback=brookesia.start_service('AudioPlayback');paused=false;cache={};theme();text('voice/label',voice?'语音提示：开':'语音提示：关');for(const action of ['voice','replay','minus','plus'])call(gui,'SubscribeAction',{Action:action});tick();period=call(timer,'StartPeriodic',{Name:'navigation',IntervalMs:1000});return true;},
 on_action(name){if(name==='replay'){const s=call(modes,'GetNavigationState');if(s.received&&!s.stale&&s.phase!==2)speak(s,Number.isInteger(s.turn)&&s.turn>=0&&s.turn<8?s.turn:7,true);return true;}if(name==='minus'||name==='plus'){const m=call(modes,'GetState');call(playback,'SetVolume',{Volume:Math.max(0,Math.min(100,m.resume_volume+(name==='plus'?5:-5)))});tick();return true;}if(name==='voice'){voice=!voice;text('voice/label',voice?'语音提示：开':'语音提示：关');if(!voice)stopSpeech();else{lastPrompt='';lastStage=-1;lastSpeech=0;tick();}}return true;},
 on_timer(){tick();return true;},
 on_pause(){paused=true;stopSpeech();return true;},
 on_resume(){paused=false;cache={};theme();tick();return true;},
 on_stop(){paused=true;stopSpeech();if(period)try{call(timer,'Stop',{TimerId:period});}catch(_){}period=0;return true;}
};
})();
