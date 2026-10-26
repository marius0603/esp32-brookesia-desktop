(function () {
'use strict';
let gui, assistant, audio, modes, timer, timerId=0, hidden=false, cache={}, state={}, volume=20;
function call(h,name,args){const r=JSON.parse(brookesia.call_function(h,name,JSON.stringify(args||{})));if(!r.success)throw new Error(r.error||r.error_message||name);return r.data;}
function text(id,value){value=String(value||'');if(hidden||cache[id]===value)return;call(gui,'SetText',{Path:'/main/'+id,Text:value});cache[id]=value;}
function truncate(s,n){s=String(s||'');return s.length>n?s.slice(0,n-1)+'…':s;}
function poll(){
  state=call(assistant,'GetState')||{};
  text('status',state.message||'点击连接小智');
  text('code',state.state==='Activation'?(state.activation_code||'等待激活码'):'');
  text('user',state.user_text?'你：'+truncate(state.user_text,45):'');
  text('answer',truncate(state.answer,115)||(state.state==='Activation'?'登录 xiaozhi.me\n添加设备，输入上方激活码':'点击说话，再次点击发送\n录音期间才会上传语音'));
  text('controls/talk/label',state.state==='Listening'?'发送':state.state==='Speaking'?'打断说话':'说话');
  text('tools/connect/label',state.active?'断开':'连接');
  volume=call(audio,'GetVolume');
  const sound=call(modes,'GetState');
  text('volume',sound.do_not_disturb?'音量 '+sound.resume_volume+'% · 勿扰静音':'音量 '+volume+'%');
  const width=state.state==='Listening'||state.state==='Testing'?Math.max(0,Math.min(280,Math.round((Number(state.level)||0)*2.8))):0;
  if(cache.level!==width&&!hidden){call(gui,'SetBinding',{Path:'/main/meter/fill',Key:'width',Value:String(width)});cache.level=width;}
}
function invoke(name){call(assistant,name);poll();}
function action(name){
  if(name==='connect')invoke(state.active?'Disconnect':'Connect');
  else if(name==='talk'){
    if(state.state==='Listening')invoke('StopListening');
    else if(state.channel)invoke('StartListening');
    else if(!state.active)invoke('Connect');
    else text('status',state.state==='Activation'?'请先在小智网站完成激活':'正在连接，请稍候');
  }else if(name==='cancel')invoke(state.channel?'Interrupt':'Disconnect');
  else if(name==='test'){
    if(state.active){text('status','请先断开连接，再测试麦克风');return;}
    invoke('TestMicrophone');
  }else if(name==='quieter'||name==='louder'){
    volume=call(audio,'GetVolume');volume=Math.max(0,Math.min(100,volume+(name==='louder'?5:-5)));call(audio,'SetVolume',{Volume:volume});volume=call(audio,'GetVolume');text('volume','音量 '+volume+'%');
  }
}
globalThis.brookesia_app={
  on_start(){
    hidden=false;cache={};gui=brookesia.start_service('SystemGui');assistant=brookesia.start_service('VoiceAssistant');
    audio=brookesia.start_service('AudioPlayback');modes=brookesia.start_service('DeviceModes');timer=brookesia.start_service('SystemTimer');
    for(const name of ['connect','talk','cancel','test','quieter','louder'])call(gui,'SubscribeAction',{Action:name});
    try{volume=call(audio,'GetVolume');}catch(_){}
    // Leaving the audiobook screen already saved its bookmark; release its codec worker.
    try{const book=brookesia.start_service('Audiobook');if(call(book,'GetState').active)call(book,'Stop');}catch(_){}
    poll();
    if(!state.active)try{invoke('Connect');}catch(e){text('status',String(e));}
    timerId=call(timer,'StartPeriodic',{Name:'voice-assistant',IntervalMs:250});return true;
  },
  on_timer(){if(!hidden)try{poll();}catch(e){text('status',String(e));}return true;},
  on_action(name){try{action(name);}catch(e){text('status',String(e));}return true;},
  on_pause(){hidden=true;try{call(assistant,'Disconnect');}catch(_){}return true;},
  on_resume(){hidden=false;cache={};poll();return true;},
  on_stop(){try{call(assistant,'Disconnect');}catch(_){}try{if(timerId)call(timer,'Stop',{TimerId:timerId});}catch(_){}timerId=0;return true;}
};
})();
