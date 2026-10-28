(function(){
'use strict';
let gui,policy,timer,timerId=0,token='',pin='',first='',purpose='',page='gate',hidden=false,state={},cache={},idleTicks=0,assistantArmed=0,notice='';
function call(h,name,args){const pinWork=h===policy&&['SetupPin','VerifyPin','ChangePin'].indexOf(name)>=0;
 const r=JSON.parse(brookesia.call_function(h,name,JSON.stringify(args||{}),pinWork?15000:3000));if(!r.success)throw new Error(r.error||r.error_message||name);return r.data;}
function text(path,value){value=String(value);if(hidden||cache[path]===value)return;call(gui,'SetText',{Path:'/main/'+path,Text:value});cache[path]=value;}
function show(next){call(gui,'SetBindings',{Updates:['gate','control','apps','times'].map(p=>({Path:'/main/'+p,Key:'hidden',Value:p===next?'false':'true'}))});page=next;}
function message(s){text('status',s);}
function read(){state=call(policy,'GetState');return state;}
function lock(){if(token)try{call(policy,'Lock',{Token:token});}catch(_){}token='';pin='';first='';purpose='';notice='';idleTicks=0;show('gate');render();}
function render(){
 text('title',page==='gate'?'家长验证':'儿童模式');
 if(page==='gate'){
  text('gate/dots',pin?new Array(pin.length+1).join('* '):'------');
  let prompt=purpose==='change'?(first?'再次输入新 PIN':'设置新的六位 PIN'):
      state.configured?'输入家长 PIN 后点确定':first?'再输入一次相同 PIN 后点确定':'首次使用：设置六位 PIN';
  if(state.locked_seconds>0)prompt='请 '+state.locked_seconds+' 秒后再试';
  message(notice||prompt);return;
 }
 message(state.resting?'当前处于休息限制':state.enabled?(state.daily_minutes?'今日还可使用 '+Math.ceil(state.remaining_seconds/60)+' 分钟':'儿童模式已开启'):'家长模式：完整桌面');
 text('control/mode/label',state.enabled?'关闭儿童模式':'开启儿童模式');
 text('control/volume','音量上限 '+state.max_volume+'%');
 text('control/limit',state.daily_minutes?'每日 '+state.daily_minutes+' 分钟':'时长不限制');
 for(const pair of [['book','听书','allow_audiobook'],['weather','天气','allow_weather'],['clock','时钟','allow_clock'],['assistant','小马助手','allow_assistant'],['learning','轻学习','allow_learning']])
   text('apps/'+pair[0]+'/label',pair[1]+'：'+(state[pair[2]]?'允许':'关闭'));
 text('times/night/label','夜间休息：'+(state.night_enabled?'开启':'关闭'));
 text('times/start','开始 '+('0'+state.night_start).slice(-2)+':00');
 text('times/end','结束 '+('0'+state.night_end).slice(-2)+':00');
 if(page==='times'&&state.night_enabled&&!state.clock_ready)message('时间未同步，儿童应用暂时休息');
}
function save(settings){call(policy,'Configure',{Token:token,Settings:settings});read();render();}
function submit(){
 if(pin.length!==6){message('请输入六位数字');return;}
 message('正在校验，请稍候…');
 if(!state.configured||purpose==='change'){
  if(!first){first=pin;pin='';render();return;}
  if(pin!==first){pin='';first='';notice='两次 PIN 不同，请重新设置';render();return;}
  if(purpose==='change')call(policy,'ChangePin',{Token:token,Pin:pin});
  else token=call(policy,'SetupPin',{Pin:pin}).token;
 }else token=call(policy,'VerifyPin',{Pin:pin}).token;
 pin='';first='';purpose='';idleTicks=0;read();show('control');render();
}
function action(name){
 idleTicks=0;notice='';
 if(page==='gate'){
  if(/^digit[0-9]$/.test(name)){if(pin.length<6)pin+=name.slice(5);render();}
  else if(name==='erase'){pin=pin.slice(0,-1);render();}
  else if(name==='enter')submit();return;
 }
 if(name==='lock'){lock();return;}
 if(name==='mode')save({enabled:!state.enabled});
 else if(name==='apps'){show('apps');render();}
 else if(name==='time'){show('times');render();}
 else if(name==='back_apps'||name==='back_time'){show('control');render();}
 else if(name==='change'){pin='';first='';purpose='change';show('gate');render();}
 else if(name==='reset'){call(policy,'ResetUsage',{Token:token});read();render();message('今日时长已重置');}
 else if(name==='night')save({night_enabled:!state.night_enabled});
 else if(name==='volume_minus'||name==='volume_plus')save({max_volume:Math.max(10,Math.min(60,state.max_volume+(name==='volume_plus'?10:-10)))});
 else if(name==='limit_minus'||name==='limit_plus'){
  const choices=[0,10,20,30,45,60,90,120];let i=choices.indexOf(state.daily_minutes);if(i<0)i=3;
  save({daily_minutes:choices[(i+(name==='limit_plus'?1:choices.length-1))%choices.length]});
 }else if(name.indexOf('start_')===0||name.indexOf('end_')===0){
  const key=name.indexOf('start_')===0?'night_start':'night_end';const v=(state[key]+(name.endsWith('_plus')?1:23))%24;
  const params={};params[key]=v;save(params);
 }else{
  const keys={book:'allow_audiobook',weather:'allow_weather',clock:'allow_clock',assistant:'allow_assistant',learning:'allow_learning'};
  if(keys[name]){
   if(name==='assistant'&&!state.allow_assistant){
    if(!assistantArmed||Date.now()-assistantArmed>8000){assistantArmed=Date.now();message('再次点击开启：语音会上传小智');return;}
    assistantArmed=0;
   }
   const p={};p[keys[name]]=!state[keys[name]];save(p);
  }
 }
}
globalThis.brookesia_app={
 on_start(){hidden=false;cache={};gui=brookesia.start_service('SystemGui');policy=brookesia.start_service('ChildMode');timer=brookesia.start_service('SystemTimer');
  const actions=['erase','enter','mode','apps','time','lock','back_apps','back_time','change','reset','night','book','weather','clock','assistant','learning','volume_minus','volume_plus','limit_minus','limit_plus','start_minus','start_plus','end_minus','end_plus'];
  for(let i=0;i<10;i++)actions.push('digit'+i);
  for(const a of actions)call(gui,'SubscribeAction',{Action:a});
  token='';pin='';first='';purpose='';notice='';idleTicks=0;read();show('gate');render();timerId=call(timer,'StartPeriodic',{Name:'child-mode',IntervalMs:1000});return true;
 },
 on_action(name){try{action(name);}catch(e){pin='';first='';notice=String(e.message||e);if(/timeout|超时/i.test(notice))notice='校验等待超时，请稍后再试';if(notice.indexOf('重新验证')>=0){token='';purpose='';show('gate');}try{read();render();}catch(_){}message(notice);}return true;},
 on_timer(){if(hidden)return true;try{if(token&&++idleTicks>=45)lock();else if(page==='gate'){read();render();}}catch(_){}return true;},
 on_pause(){try{lock();}catch(_){}hidden=true;return true;},
 on_resume(){hidden=false;cache={};read();show('gate');render();return true;},
 on_stop(){try{lock();}catch(_){}try{if(timerId)call(timer,'Stop',{TimerId:timerId});}catch(_){}hidden=true;token='';pin='';first='';return true;}
};
})();
