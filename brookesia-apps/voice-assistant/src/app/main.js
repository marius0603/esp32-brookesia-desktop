(function () {
'use strict';
let gui, assistant, pcAssistant, cloudAssistant, storage, backend='pc', audio, modes, timer, timerId=0, hidden=false, cache={}, state={}, volume=20;
function call(h,name,args){const r=JSON.parse(brookesia.call_function(h,name,JSON.stringify(args||{})));if(!r.success)throw new Error(r.error||r.error_message||name);return r.data;}
const paths={status:'header/state/status',user:'conversation/user',answer:'conversation/answer',welcome:'conversation/welcome',volume:'footer/volume','backend/label':'footer/backend/label'};
function text(id,value){value=String(value||'');if(hidden||cache[id]===value)return;call(gui,'SetText',{Path:'/main/'+(paths[id]||id),Text:value});cache[id]=value;}
function bind(path,key,value){const id=path+':'+key;value=String(value);if(hidden||cache[id]===value)return;call(gui,'SetBinding',{Path:'/main/'+path,Key:key,Value:value});cache[id]=value;}
function truncate(s,n){s=String(s||'');return s.length>n?s.slice(0,n-1)+'…':s;}
function poll(){
  state=call(assistant,'GetState')||{};
  const statuses={Idle:'未连接',Connecting:'连接中',Ready:'就绪',Starting:'准备中',Listening:'聆听中',Uploading:'上传中',Thinking:'思考中',Speaking:'回答中',Activation:'待激活',Error:'异常',Closing:'断开中'};
  text('backend/label',backend==='pc'?'电脑模式':'小智模式');
  const activation=state.state==='Activation',error=state.error||((state.state==='Error'||(state.stack_limit_hit&&state.state==='Ready'))?state.message:'');
  text('status',error?'异常':statuses[state.state]||(state.channel?'就绪':'连接中'));
  const hasConversation=Boolean(state.user_text||state.answer||activation||error);
  text('user',activation?'激活码 '+(state.activation_code||'--'):state.user_text?'你：'+truncate(state.user_text,28):'');
  text('answer',truncate(error||(activation?'xiaozhi.me':state.answer),42));
  text('welcome',state.state==='Listening'?'我在听':state.state==='Thinking'?'让我想一想':state.state==='Uploading'?'正在处理':'你好，我是小马。');
  for(const name of ['avatar','welcome'])bind('conversation/'+name,'hidden',hasConversation);
  for(const name of ['user','divider','answer'])bind('conversation/'+name,'hidden',!hasConversation);
  bind('header/state/dot','color',error?'#ef929b':state.channel?'#78dfbb':'#e2c283');
  text('controls/talk/label',state.state==='Listening'?'发送':state.state==='Starting'?'准备中':state.state==='Uploading'?'上传中':activation?'待激活':!state.active?'连接':!state.channel?'连接中':'说话');
  volume=call(audio,'GetVolume');
  const sound=call(modes,'GetState');
  text('volume',sound.do_not_disturb?'音量 '+sound.resume_volume+'% · 静音':'音量 '+volume+'%');
  const width=state.state==='Listening'?Math.max(0,Math.min(360,Math.round((Number(state.level)||0)*3.6))):0;
  if(cache.level!==width&&!hidden){call(gui,'SetBinding',{Path:'/main/meter/fill',Key:'width',Value:String(width)});cache.level=width;}
}
function invoke(name){call(assistant,name);poll();}
function action(name){
  if(name==='backend'){
    if(state.active)call(assistant,'Disconnect');
    backend=backend==='pc'?'xiaozhi':'pc';assistant=backend==='pc'?pcAssistant:cloudAssistant;cache={};
    try{call(storage,'FSWriteText',{Path:'/littlefs/voice-assistant-backend.json',Data:JSON.stringify({backend})});}catch(_){}
    poll();if(!state.active)invoke('Connect');return;
  }
  if(name==='talk'){
    if(state.state==='Starting'||state.state==='Uploading')return;
    if(state.state==='Listening')invoke('StopListening');
    else if(state.channel)invoke('StartListening');
    else if(!state.active)invoke('Connect');
    else text('status',state.state==='Activation'?'待激活':'连接中');
  }
}
globalThis.brookesia_app={
  on_start(){
    hidden=false;cache={};gui=brookesia.start_service('SystemGui');pcAssistant=brookesia.start_service('LocalVoice');cloudAssistant=brookesia.start_service('VoiceAssistant');storage=brookesia.start_service('Storage');
    backend='pc';try{const saved=JSON.parse(call(storage,'FSReadText',{Path:'/littlefs/voice-assistant-backend.json'}));if(saved.backend==='xiaozhi')backend='xiaozhi';}catch(_){}
    assistant=backend==='pc'?pcAssistant:cloudAssistant;
    audio=brookesia.start_service('AudioPlayback');modes=brookesia.start_service('DeviceModes');timer=brookesia.start_service('SystemTimer');
    for(const name of ['talk','backend'])call(gui,'SubscribeAction',{Action:name});
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
  on_resume(){hidden=false;cache={};poll();if(!state.active)try{invoke('Connect');}catch(e){text('status',String(e));}return true;},
  on_stop(){try{call(assistant,'Disconnect');}catch(_){}try{if(timerId)call(timer,'Stop',{TimerId:timerId});}catch(_){}timerId=0;return true;}
};
})();
