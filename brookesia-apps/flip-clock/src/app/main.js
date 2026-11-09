(function () {
'use strict';
let gui,timer,storage,paused=false,shown=null,second=-1,flips=[],fx=0,started=0,frames=0,reported=false;
function call(h,n,a){const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(a||{})));if(!r.success)throw new Error(r.error||n);return r.data;}
function source(i,half,value){return (i<4?'big':'small')+'_'+half+'_'+value;}
function image(i,part,value,half){call(gui,'SetViewSrc',{Path:'/main/flip/d'+i+'/'+part,Src:source(i,half,value)});}
function bind(i,key,value){return {Path:'/main/flip/d'+i+'/flap',Key:key,Value:String(value)};}
function digits(now){if(now<1704067200000)return '----';const d=new Date(now+8*3600000);return String(d.getUTCHours()).padStart(2,'0')+String(d.getUTCMinutes()).padStart(2,'0');}
function height(i){return 75;}
function record(){try{call(storage,'FSWriteText',{Path:'/littlefs/clock-state.json',Data:JSON.stringify({version:1,time:Date.now(),digits:face===0?shown:digits(Date.now()),face,paw_frame:pawFrame,frames,paused,timezone:'Asia/Shanghai'})});}catch(_){} }
function stopFx(){if(fx){try{call(timer,'Stop',{TimerId:fx});}catch(_){}fx=0;}}
function finish(){
  if(!flips.length){stopFx();return;}
  const updates=[];
  for(const f of flips){image(f.i,'bottom',f.next,'bottom');updates.push(bind(f.i,'opacity',0));}
  call(gui,'SetBindings',{Updates:updates});flips=[];stopFx();
  if(!reported&&frames>0){reported=true;record();}
}
function render(value){
  finish();const updates=[];
  for(let i=0;i<4;i++){image(i,'top',value[i],'top');image(i,'bottom',value[i],'bottom');updates.push(bind(i,'opacity',0));}
  call(gui,'SetBindings',{Updates:updates});shown=value;
}
function tick(){
  if(paused)return;const now=Date.now(),s=Math.floor(now/60000);if(s===second)return;
  const value=digits(now),sequential=s-second===1;second=s;
  if(shown===null||shown.includes('-')||value.includes('-')||!sequential){render(value);return;}
  finish();const updates=[];
  for(let i=0;i<4;i++)if(shown[i]!==value[i]){
    const h=height(i);flips.push({i,next:value[i],old:shown[i],half:0});
    image(i,'top',value[i],'top');image(i,'flap',shown[i],'top');
    updates.push(bind(i,'y',0),bind(i,'height',h),bind(i,'opacity',255));
  }
  shown=value;
  if(flips.length){call(gui,'SetBindings',{Updates:updates});started=now;fx=call(timer,'StartPeriodic',{Name:'flip',IntervalMs:40});}
}
function animate(){
  if(paused||!flips.length)return;const p=Math.max(0,(Date.now()-started)/360);frames++;
  if(p>=1){finish();return;}
  const updates=[];
  for(const f of flips){
    const h=height(f.i);
    if(p<.5){const visible=Math.max(1,Math.round(h*Math.cos(p*Math.PI)));updates.push(bind(f.i,'y',h-visible),bind(f.i,'height',visible));}
    else {if(!f.half){image(f.i,'flap',f.next,'bottom');f.half=1;}const visible=Math.max(1,Math.round(h*Math.sin((p-.5)*Math.PI)));updates.push(bind(f.i,'y',h+2),bind(f.i,'height',visible));}
  }
  call(gui,'SetBindings',{Updates:updates});
}
let face=0,wifi,http,modes,press=null,lastSwipe=-1000,lastSecond=-1,pawFrame=-1,nextStatus=0,asleep=false,weather=null,pending=null,nextFetch=0,cache={};
const PLACE={city:'上海',latitude:31.2304,longitude:121.4737};let place=PLACE;
function read(p){try{return JSON.parse(call(storage,'FSReadText',{Path:p}));}catch(_){return null;}}
function set(path,key,value){value=String(value);const k=path+':'+key;if(cache[k]===value)return;call(gui,'SetBinding',{Path:'/main/'+path,Key:key,Value:value});cache[k]=value;}
function text(path,value){value=String(value);if(cache[path]===value)return;call(gui,'SetText',{Path:'/main/'+path,Text:value});cache[path]=value;}
function condition(c){if(c===0)return '晴';if(c<3)return '多云';if(c===3)return '阴';if(c<50)return '雾';if(c<70)return '雨';if(c<80)return '雪';if(c<85)return '阵雨';if(c<90)return '阵雪';return '雷雨';}
function validPlace(p){return p&&typeof p.city==='string'&&Number.isFinite(p.latitude)&&Math.abs(p.latitude)<=90&&Number.isFinite(p.longitude)&&Math.abs(p.longitude)<=180;}
function cancel(){if(pending)try{call(http,'CancelRequest',{RequestId:pending.id});}catch(_){}pending=null;}
function status(now){
 if(now<nextStatus)return;nextStatus=now+5000;
 let online=false;try{online=call(wifi,'GetGeneralState')==='Connected';}catch(_){}
 text('status/network',online?'Wi-Fi 已连接':'Wi-Fi 未连接');
 try{const m=call(modes,'GetState');asleep=!!m.screen_asleep;const b=Number(m.battery_status),v=b&255;text('status/battery',v<=100?(b&256?'充电 ':'电量 ')+v+'%':v===102?'USB供电':'电量 --');}catch(_){}
 if(weather){text('status/weather',(place.city||'上海').slice(0,4)+'  '+weather.temperature.toFixed(0)+'°C  '+condition(weather.code)+(face===1&&(!online||now-weather.received_at>1800000)?' 缓存':''));text('status/weatherAge',(now-weather.received_at>1800000?'天气缓存已过期':online?'':'离线天气缓存'));}
 else{text('status/weather','天气待更新');text('status/weatherAge',online?'正在获取天气':'请连接 Wi-Fi');}
 if(pending&&now-pending.started>25000){cancel();nextFetch=now+60000;}
 if(online&&!pending&&now>=nextFetch){
  nextFetch=now+600000;
  try{const url='https://api.open-meteo.com/v1/forecast?latitude='+place.latitude+'&longitude='+place.longitude+'&current=temperature_2m,weather_code&timezone=auto';
   pending={id:call(http,'RequestAsync',{Request:{url,method:'Get',timeout_ms:15000,headers:{},body:''}}),started:now};
  }catch(_){nextFetch=now+60000;}
 }
}
function extraTick(){
 if(paused)return;const now=Date.now();if(face===0){tick();return;}status(now);if(asleep)return;
 const d=new Date(now+8*3600000),valid=now>=1704067200000;
 text('status/date',valid?(d.getUTCMonth()+1)+'月'+d.getUTCDate()+'日  周'+'日一二三四五六'[d.getUTCDay()]:'等待校时');
 if(face===1){
  const sec=Math.floor(now/1000);if(sec===lastSecond)return;lastSecond=sec;
  const h=d.getUTCHours()%12,m=d.getUTCMinutes(),v=d.getUTCSeconds();
  const points=(angle,length,tail)=>{const a=angle*Math.PI/180;return JSON.stringify([{x:Math.round(170-tail*Math.sin(a)),y:Math.round(170+tail*Math.cos(a))},{x:Math.round(170+length*Math.sin(a)),y:Math.round(170-length*Math.cos(a))}]);};
  if(valid){call(gui,'SetBindings',{Updates:[['hour',h*30+m*.5+v/120,93,10],['minute',m*6+v*.1,133,10],['second',v*6,145,20]].map(a=>({Path:'/main/analog/'+a[0],Key:'points',Value:points(a[1],a[2],a[3])}))});}
 }else{
  const value=digits(now);text('companion/time',value.slice(0,2)+':'+value.slice(2));
  const phase=Math.floor(now/250)%4;if(phase!==pawFrame){pawFrame=phase;set('companion/leftPaw','y',[371,376,373,369][phase]);set('companion/rightPaw','y',[373,369,371,376][phase]);const blink=Math.floor(now/250)%20===0;for(const eye of ['leftEye','rightEye']){set('companion/'+eye,'height',blink?3:18);set('companion/'+eye,'y',blink?331:323);set('companion/'+eye+'/glint','hidden',blink);}}
 }
}
function select(next,persist){
 finish();face=(next+3)%3;cache={};lastSecond=-1;pawFrame=-1;second=-1;shown=null;nextStatus=0;
 for(const [id,i] of [['flip',0],['analog',1],['companion',2]])set(id,'hidden',face!==i);
 set('status','hidden',face===0);set('status/date','y',face===1?415:91);
 for(let i=0;i<3;i++){set('status/page'+i,'color',i===face?'#d7e3f9':'#536078');set('status/page'+i,'hidden',face===1);}
 set('status/weather','y',face===1?444:424);set('status/weatherAge','hidden',face===1);
 if(face===0)cancel();extraTick();
 if(persist)try{call(storage,'FSWriteText',{Path:'/littlefs/clock-face.json',Data:JSON.stringify({face})});}catch(_){}
 record();
}
globalThis.brookesia_app={
 on_start(){
  gui=brookesia.start_service('SystemGui');timer=brookesia.start_service('SystemTimer');storage=brookesia.start_service('Storage');brookesia.start_service('SNTP');
  wifi=brookesia.start_service('Wifi');http=brookesia.start_service('Http');modes=brookesia.start_service('DeviceModes');
  for(const e of ['RequestCompleted','RequestFailed','RequestCanceled'])brookesia.subscribe_event(http,e);
  for(const a of ['facePress','faceRelease','faceCancel'])call(gui,'SubscribeAction',{Action:a});
  const settings=read('/littlefs/weather-settings.json'),old=read('/littlefs/weather-cache.json'),own=read('/littlefs/clock-weather.json');
  if(old&&old.mode===(settings&&settings.mode==='auto'?'auto':'shanghai')&&validPlace(old.location)){place=old.location;const c=old.data&&old.data.current;if(c&&Number.isFinite(c.temperature_2m)&&Number.isInteger(c.weather_code))weather={temperature:c.temperature_2m,code:c.weather_code,received_at:old.received_at||0};}
  if(own&&validPlace(own.place)&&own.place.latitude===place.latitude&&own.place.longitude===place.longitude&&own.weather&&Number.isFinite(own.weather.temperature)&&Number.isInteger(own.weather.code)&&(!weather||own.weather.received_at>weather.received_at)){place=own.place;weather=own.weather;}
  nextFetch=weather?weather.received_at+600000:0;const pref=read('/littlefs/clock-face.json');paused=false;select(pref&&Number.isInteger(pref.face)&&pref.face>=0&&pref.face<3?pref.face:0,false);call(timer,'StartPeriodic',{Name:'clock',IntervalMs:250});return true;
 },
 on_action(name,path,payload){
  if(name==='faceCancel'){press=null;return true;}
  let p;try{p=typeof payload==='string'?JSON.parse(payload):payload;}catch(_){press=null;return true;}
  if(!p||!Number.isFinite(p.x)||!Number.isFinite(p.y))return true;
  if(name==='facePress'){press={x:p.x,y:p.y};return true;}
  if(name==='faceRelease'&&press){const dx=p.x-press.x,dy=p.y-press.y;press=null;if(Math.abs(dx)>=48&&Math.abs(dx)>Math.abs(dy)*1.25&&Date.now()-lastSwipe>=300){lastSwipe=Date.now();select(face+(dx<0?1:-1),true);}}
  return true;
 },
 on_event(service,event,payload){
  if(paused||service!=='Http'||!pending)return true;
  try{const v=JSON.parse(payload);if(v.RequestId!==pending.id)return true;pending=null;const r=v.Response||{};if(r.status_code!==200||r.error!=='Ok')throw Error('weather');const d=JSON.parse(r.body),c=d.current;if(!c||!Number.isFinite(c.temperature_2m)||!Number.isInteger(c.weather_code)||c.temperature_2m< -100||c.temperature_2m>70)throw Error('weather');weather={temperature:c.temperature_2m,code:c.weather_code,received_at:Date.now()};call(storage,'FSWriteText',{Path:'/littlefs/clock-weather.json',Data:JSON.stringify({place,weather})});nextStatus=0;extraTick();}catch(_){pending=null;nextFetch=Date.now()+60000;}return true;
 },
 on_timer(id,name){if(name==='flip')animate();else extraTick();return true;},
 on_pause(){finish();paused=true;press=null;stopFx();cancel();return true;},
 on_resume(){paused=false;reported=false;select(face,false);return true;},
 on_stop(){paused=true;press=null;stopFx();cancel();flips=[];return true;}
};
})();
