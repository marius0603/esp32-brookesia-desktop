(function () {
'use strict';
const ROOT='/sdcard/pets/xiaoli/', FRAME_IDS=['pet_idle_0','pet_idle_1','pet_idle_2','pet_eat_0','pet_eat_1','pet_eat_2','pet_sleep_0','pet_sleep_1'];
const DEFAULTS={schema:1,timezone:'Asia/Shanghai',utc_offset_minutes:480,meals:[{name:'早餐',start:450,duration:30},{name:'午餐',start:720,duration:30},{name:'晚餐',start:1110,duration:30}],sleep:{start:1320,end:420}};
let gui,timer,storage,system,timerId=0,hidden=true,background=false,panel=false,config=DEFAULTS,override=null,mode='',phaseStart=0,cache={},frames=0,lastReport=0,lastNow=0,lastFocus=0,configError=false;
let breathId=0,fadeId=0,fadeUntil=0;
function call(h,n,a){const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(a||{})));if(!r.success)throw new Error(r.error||r.error_message||n);return r.data;}
function validMinute(v){return Number.isInteger(v)&&v>=0&&v<1440;}
function validate(c){
 if(!c||c.schema!==1||c.timezone!=='Asia/Shanghai'||c.utc_offset_minutes!==480||!Array.isArray(c.meals)||c.meals.length!==3||!c.sleep||!validMinute(c.sleep.start)||!validMinute(c.sleep.end)||c.sleep.start===c.sleep.end)throw new Error('作息格式不正确');
 for(const m of c.meals)if(!m||!['早餐','午餐','晚餐'].includes(m.name)||!validMinute(m.start)||!Number.isInteger(m.duration)||m.duration<1||m.duration>60)throw new Error('用餐时间不正确');
 if(new Set(c.meals.map(m=>m.name)).size!==3)throw new Error('用餐名称重复');
 return c;
}
function hm(minute){return String(Math.floor(minute/60)).padStart(2,'0')+':'+String(minute%60).padStart(2,'0');}
function clock(now){
 if(!Number.isFinite(now)||now<1704067200000||now>=4102444800000)return null;
 const d=new Date(now+config.utc_offset_minutes*60000);
 return {minute:d.getUTCHours()*60+d.getUTCMinutes(),time:String(d.getUTCHours()).padStart(2,'0')+':'+String(d.getUTCMinutes()).padStart(2,'0')};
}
function inWindow(minute,start,end){return start<end?minute>=start&&minute<end:minute>=start||minute<end;}
function scheduled(now){
 const c=clock(now);if(!c)return {mode:'idle',label:'等待校时',time:'--:--'};
 if(inWindow(c.minute,config.sleep.start,config.sleep.end))return {mode:'sleep',label:'睡个好觉',time:c.time};
 for(const m of config.meals)if((c.minute-m.start+1440)%1440<m.duration)return {mode:'eat',label:'吃'+m.name,time:c.time};
 return {mode:'idle',label:'陪你一起',time:c.time};
}
function text(path,value){const key='text:'+path;if(cache[key]===value)return;call(gui,'SetText',{Path:'/main/'+path,Text:value});cache[key]=value;}
function bind(path,key,value){value=String(value);const id=path+':'+key;if(cache[id]===value)return;call(gui,'SetBinding',{Path:'/main/'+path,Key:key,Value:value});cache[id]=value;}
function report(now){
 try{call(storage,'FSWriteText',{Path:ROOT+'state.json',Data:JSON.stringify({schema:1,version:'0.1.2',mode,frames,paused:hidden||background,panel,clock_synced:!!clock(now),time:now,temporary:!!override,config_fallback:configError,native_motion:true})});lastReport=now;}catch(_){}
}
function stopTimer(){if(timerId){try{call(timer,'Stop',{TimerId:timerId});}catch(_){}timerId=0;}}
function startTimer(interval){if(!timerId)timerId=call(timer,'StartPeriodic',{Name:'pet',IntervalMs:interval||50});}
function stopMotion(){
 for(const id of [breathId,fadeId])if(id)try{call(gui,'StopAnimation',{AnimationId:id});}catch(_){}
 breathId=0;fadeId=0;fadeUntil=0;delete cache.motion;
}
function motion(current){
 if(cache.motion===current)return;
 stopMotion();bind('home/pet','y',80);
 breathId=call(gui,'StartViewAnimation',{Path:'/main/home/pet',Animation:{property:'y',from:80,to:current==='happy'?72:current==='eat'?78:76,duration:current==='eat'?420:current==='happy'?350:current==='sleep'?2000:1600,easing:'easeInOut',playback:true,repeat:65535}});
 cache.motion=current;
}
function showPose(src,now){
 if(cache.src===src)return;
 const commands=[];
 if(fadeId&&now<fadeUntil)commands.push({Name:'StopAnimation',Params:{AnimationId:fadeId}});
 if(!cache.src||mode==='eat'){
  // Eating uses a single opaque pose, never two translucent muzzles or bowls.
  commands.push({Name:'SetViewSrc',Params:{Path:'/main/home/pet/base',Src:src}},{Name:'SetViewSrc',Params:{Path:'/main/home/pet/blend',Src:src}},{Name:'SetBindings',Params:{Updates:[{Path:'/main/home/pet/blend',Key:'opacity',Value:'0'}]}});
 }else{
  // The backend blends neighbouring poses; JavaScript does not render the tween frames.
  commands.push({Name:'SetViewSrc',Params:{Path:'/main/home/pet/base',Src:cache.src}},{Name:'SetViewSrc',Params:{Path:'/main/home/pet/blend',Src:src}},{Name:'SetBindings',Params:{Updates:[{Path:'/main/home/pet/blend',Key:'opacity',Value:'0'}]}},{Name:'StartViewAnimation',Params:{Path:'/main/home/pet/blend',Animation:{property:'opacity',from:0,to:255,duration:mode==='idle'?65:145,easing:'easeInOut'}}});
 }
 const result=call(gui,'ExecuteBatch',{Commands:commands});
 if(!result.Success)throw new Error('动画更新失败');
 const animation=result.Results.find(r=>r.Name==='StartViewAnimation');fadeId=animation?animation.Data.AnimationId:0;fadeUntil=now+(mode==='idle'?65:145);
 cache.src=src;frames++;
}
function foreground(){
 const now=Date.now();if(now-lastFocus<1000&&now>=lastFocus)return;lastFocus=now;
 const active=call(system,'GetActiveApp');
 const away=!active||!active.manifest||active.manifest.id!=='local.virtualpet';
 if(away===background)return;
 background=away;override=null;stopTimer();
 if(away){stopMotion();try{call(gui,'ReleaseImages',{Ids:FRAME_IDS});}catch(_){}startTimer(1000);}
 else{call(gui,'PreloadImages',{Ids:FRAME_IDS});cache={};mode='';startTimer();}
 report(now);
}
function pose(current,elapsed){
 if(current==='eat')return ['pet_eat_0','pet_eat_1','pet_eat_0','pet_eat_1','pet_eat_0','pet_eat_1','pet_eat_2','pet_eat_1'][Math.floor(elapsed/160)%8];
 if(current==='sleep')return FRAME_IDS[6+(Math.floor(elapsed/1600)%2)];
 if(current==='happy')return Math.floor(elapsed/600)%2?'pet_idle_2':'pet_idle_0';
 const p=elapsed%4200;return p<3500?'pet_idle_0':p<3600?'pet_idle_1':p<3750?'pet_idle_2':p<3850?'pet_idle_1':'pet_idle_0';
}
function tick(){
 if(hidden||background)return;
 const now=Date.now();
 // A corrected network clock must neither extend nor revive temporary interactions.
 if(lastNow&&(now<lastNow||now-lastNow>60000))override=null;
 lastNow=now;
 const base=scheduled(now);
 if(override&&now>=override.until)override=null;
 if(override&&!override.preview&&base.mode==='sleep')override=null;
 const current=override?override.mode:base.mode;
 if(mode!==current){mode=current;phaseStart=now;report(now);}
 text('clock',base.time);
 text('status',override?(override.preview?'睡觉预览':current==='eat'?'好吃好吃':'好开心呀'):base.label);
 text('hint',configError?'已使用默认作息':!clock(now)?'联网后自动校时':override&&override.preview?'稍后自动回到当前作息':'');
 if(!panel){
  const elapsed=Math.max(0,now-phaseStart),src=pose(mode,elapsed);
  motion(mode);showPose(src,now);
 }
 if(now-lastReport>=30000)report(now);
}
function showPanel(show){panel=show;if(show)stopMotion();bind('home','hidden',show);bind('schedule','hidden',!show);if(show){for(let i=0;i<3;i++)text('schedule/meal'+i,config.meals[i].name+'   '+hm(config.meals[i].start));text('schedule/sleep','睡觉   '+hm(config.sleep.start)+' - '+hm(config.sleep.end));}tick();}
function interact(name){
 if(hidden||background)return;
 if(name==='petTap')name='pet';
 const now=Date.now();
 if(name==='schedule'){showPanel(true);return;}
 if(name==='back'){showPanel(false);return;}
 if(name==='sleepPreview'){override={mode:'sleep',until:now+12000,preview:true};showPanel(false);return;}
 if(name!=='feed'&&name!=='pet')return;
 if(scheduled(now).mode==='sleep'){text('status','小栗在睡觉');return;}
 override={mode:name==='feed'?'eat':'happy',until:now+(name==='feed'?12000:6000),preview:false};tick();
}
globalThis.brookesia_app={
 on_start(){
  gui=brookesia.start_service('SystemGui');timer=brookesia.start_service('SystemTimer');storage=brookesia.start_service('Storage');system=brookesia.start_service('SystemCore');brookesia.start_service('SNTP');
  configError=false;try{const raw=call(storage,'FSReadText',{Path:ROOT+'schedule.json'});if(typeof raw!=='string'||raw.length>4096)throw new Error('Invalid schedule');config=validate(JSON.parse(raw));}catch(_){config=DEFAULTS;configError=true;}
  hidden=false;background=false;panel=false;override=null;mode='';cache={};frames=0;lastNow=0;lastReport=0;lastFocus=Date.now();
  for(const action of ['feed','pet','petTap','schedule','back','sleepPreview'])call(gui,'SubscribeAction',{Action:action});
  tick();startTimer();report(Date.now());return true;
 },
 on_timer(){if(!hidden){foreground();tick();}return true;},
 on_action(name){interact(name);return true;},
 on_pause(){hidden=true;override=null;stopTimer();stopMotion();report(Date.now());try{call(gui,'ReleaseImages',{Ids:FRAME_IDS});}catch(_){}return true;},
 on_resume(){call(gui,'PreloadImages',{Ids:FRAME_IDS});hidden=false;background=false;panel=false;override=null;mode='';cache={};lastNow=0;lastFocus=Date.now();showPanel(false);startTimer();report(Date.now());return true;},
 on_stop(){hidden=true;override=null;stopTimer();stopMotion();report(Date.now());return true;}
};
})();
