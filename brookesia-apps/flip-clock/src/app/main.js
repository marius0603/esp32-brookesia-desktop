(function () {
'use strict';
let gui,timer,storage,paused=false,shown=null,second=-1,flips=[],fx=0,started=0,frames=0,reported=false;
let nativeIds=[],nativeFlips=0;
function call(h,n,a){const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(a||{})));if(!r.success)throw new Error(r.error||n);return r.data;}
function digitRoot(){return face===2?'/main/companion/':'/main/flip/';}
function source(i,half,value){return (face===2?'clock':'big')+'_'+half+'_'+value;}
function image(i,part,value,half){call(gui,'SetViewSrc',{Path:digitRoot()+'d'+i+'/'+part,Src:source(i,half,value)});}
function bind(i,key,value){return {Path:digitRoot()+'d'+i+'/flap',Key:key,Value:String(value)};}
function digits(now){if(now<1704067200000)return face===2?'------':'----';const d=new Date(now+8*3600000);return String(d.getUTCHours()).padStart(2,'0')+String(d.getUTCMinutes()).padStart(2,'0')+(face===2?String(d.getUTCSeconds()).padStart(2,'0'):'');}
function height(i){return face===2?49:75;}
function record(){try{call(storage,'FSWriteText',{Path:'/littlefs/clock-state.json',Data:JSON.stringify({version:4,time:Date.now(),digits:face===1?digits(Date.now()):shown,face,paw_frame:pawFrame,frames,paused,timezone:'Asia/Shanghai',flip_engine:face===2?'native':'javascript',native_flips:nativeFlips,cat_updates:catUpdates,cat_max_ms:catMaxMs,cat_error:catError,cat_scene:catScene,solar:daylight(Date.now()),icons:iconState})});}catch(_){} }
function stopFx(){if(fx){try{call(timer,'Stop',{TimerId:fx});}catch(_){}fx=0;}}
function batch(commands){const r=call(gui,'ExecuteBatch',{Commands:commands});if(!r||!r.Success)throw new Error('Native flip batch failed');return r.Results||[];}
function stopNative(){for(const id of nativeIds)try{call(gui,'StopAnimation',{AnimationId:id});}catch(_){}nativeIds=[];}
function startNative(){
 const commands=[],updates=[],anim=(path,property,from,to,delay,duration,easing)=>commands.push({Name:'StartViewAnimation',Params:{Path:path,Animation:{property,from,to,delay,duration,easing}}});
 for(const f of flips){
  const root='/main/companion/d'+f.i+'/',incoming=root+'incoming';
  commands.push({Name:'SetViewSrc',Params:{Path:root+'top',Src:'clock_top_'+f.next}},{Name:'SetViewSrc',Params:{Path:root+'flap',Src:'clock_top_'+f.old}},{Name:'SetViewSrc',Params:{Path:incoming,Src:'clock_bottom_'+f.next}});
  for(const [path,key,value] of [[root+'flap','hidden',false],[root+'flap','y',0],[root+'flap','height',49],[root+'flap','opacity',255],[incoming,'hidden',false],[incoming,'y',51],[incoming,'height',1],[incoming,'opacity',0]])updates.push({Path:path,Key:key,Value:String(value)});
 }
 commands.push({Name:'SetBindings',Params:{Updates:updates}});
 for(const f of flips){const root='/main/companion/d'+f.i+'/';
  anim(root+'flap','y',0,48,0,180,'easeIn');anim(root+'flap','height',49,1,0,180,'easeIn');anim(root+'flap','opacity',255,0,179,1,'linear');
  anim(root+'incoming','opacity',0,255,180,1,'linear');anim(root+'incoming','height',1,49,180,180,'easeOut');
 }
 nativeIds=batch(commands).filter(r=>r.Name==='StartViewAnimation').map(r=>r.Data.AnimationId);
 nativeFlips+=flips.length;
}
function finish(){
  if(!flips.length){stopFx();return;}
  if(face===2){
   const commands=nativeIds.map(id=>({Name:'StopAnimation',Params:{AnimationId:id}})),hide=[];
   for(const f of flips){const root='/main/companion/d'+f.i+'/';commands.push({Name:'SetViewSrc',Params:{Path:root+'bottom',Src:'clock_bottom_'+f.next}});hide.push({Path:root+'incoming',Key:'hidden',Value:'true'},bind(f.i,'hidden',true));}
   // Visibility is never driven by the native opacity tween, so this always
   // changes the binding and hides overlays even if native geometry is midway.
   commands.push({Name:'SetBindings',Params:{Updates:hide}});batch(commands);nativeIds=[];frames+=flips.length;flips=[];stopFx();
   if(!reported){reported=true;record();}return;
  }
  const updates=[];
  for(const f of flips){image(f.i,'bottom',f.next,'bottom');updates.push(bind(f.i,'opacity',0));}
  call(gui,'SetBindings',{Updates:updates});flips=[];stopFx();
  if(!reported&&frames>0){reported=true;record();}
}
function render(value){
  finish();const updates=[];
  for(let i=0;i<value.length;i++){image(i,'top',value[i],'top');image(i,'bottom',value[i],'bottom');updates.push(bind(i,'opacity',0));if(face===2)updates.push(bind(i,'hidden',true),{Path:'/main/companion/d'+i+'/incoming',Key:'hidden',Value:'true'});}
  call(gui,'SetBindings',{Updates:updates});shown=value;
}
function tick(){
  if(paused||asleep)return;const now=Date.now(),s=Math.floor(now/(face===2?1000:60000));if(s===second)return;
  const value=digits(now),sequential=s-second===1;second=s;
  if(shown===null||shown.includes('-')||value.includes('-')||!sequential){render(value);return;}
  finish();const updates=[];
  if(face===2){
   for(let i=0;i<value.length;i++)if(shown[i]!==value[i])flips.push({i,next:value[i],old:shown[i],half:0});
   shown=value;if(flips.length){startNative();started=now;}return;
  }
  for(let i=0;i<value.length;i++)if(shown[i]!==value[i]){
    const h=height(i);flips.push({i,next:value[i],old:shown[i],half:0});
    image(i,'top',value[i],'top');image(i,'flap',shown[i],'top');
    updates.push(bind(i,'y',0),bind(i,'height',h),bind(i,'opacity',255));
  }
  shown=value;
  if(flips.length){call(gui,'SetBindings',{Updates:updates});started=now;fx=call(timer,'StartPeriodic',{Name:'flip',IntervalMs:40});}
}
function animate(){
  if(paused||asleep||!flips.length)return;const p=Math.max(0,(Date.now()-started)/360);frames++;
  if(face===2){frames--;if(p>=1)finish();return;}
  if(p>=1){finish();return;}
  const updates=[];
  for(const f of flips){
    const h=height(f.i);
    if(p<.5){const visible=Math.max(1,Math.round(h*Math.cos(p*Math.PI)));updates.push(bind(f.i,'y',h-visible),bind(f.i,'height',visible));}
    else {if(!f.half){image(f.i,'flap',f.next,'bottom');f.half=1;}const visible=Math.max(1,Math.round(h*Math.sin((p-.5)*Math.PI)));updates.push(bind(f.i,'y',h+2),bind(f.i,'height',visible));}
  }
  call(gui,'SetBindings',{Updates:updates});
}
let face=0,wifi,http,modes,press=null,lastSwipe=-1000,lastSecond=-1,pawFrame=-1,nextStatus=0,asleep=false,weather=null,pending=null,nextFetch=0,cache={},touchUntil=0;
function swipePoint(p,release){
 if(!press)return;
 const dx=p.x-press.x,dy=p.y-press.y,ax=Math.abs(dx),ay=Math.abs(dy);
 // Once a vertical gesture is established, leave it to the system.
 if(ay>=24&&ay>ax*1.2){press=null;return;}
 if(ax>=32&&ax>ay*1.1&&Date.now()-lastSwipe>=180){press=null;lastSwipe=Date.now();select(face+(dx<0?1:-1),true);}
 else if(release)press=null;
}
let catScene='',catUpdates=0,catMaxMs=0,catError='',catReported=false;
let iconState={};
const PLACE={city:'上海',latitude:31.2304,longitude:121.4737};let place=PLACE;
function read(p){try{return JSON.parse(call(storage,'FSReadText',{Path:p}));}catch(_){return null;}}
function set(path,key,value){value=String(value);const k=path+':'+key;if(cache[k]===value)return;call(gui,'SetBinding',{Path:'/main/'+path,Key:key,Value:value});cache[k]=value;}
function text(path,value){value=String(value);if(cache[path]===value)return;call(gui,'SetText',{Path:'/main/'+path,Text:value});cache[path]=value;}
function icon(path,src){const key='image:'+path;if(cache[key]===src)return;call(gui,'SetViewSrc',{Path:'/main/'+path,Src:src});cache[key]=src;iconState[path]=src;}
function weatherSymbol(code,day){
 if(code===0)return 'clear_'+(day?'day':'night');if(code===1||code===2)return 'partly_'+(day?'day':'night');
 if(code===3)return 'clouds';if(code===45||code===48)return 'fog';
 if([51,53,55,56,57,61,63,65,66,67,80,81,82].includes(code))return 'rain';
 if([71,73,75,77,85,86].includes(code))return 'snow';if([95,96,97,99].includes(code))return 'thunder';return 'unknown';
}
function weatherIcon(now){icon('status/weather/symbol','icon_weather_'+(weather?weatherSymbol(weather.code,daylight(now).day):'unknown'));}
function batterySymbol(b){
 if(!Number.isInteger(b)||b<0)return 'icon_battery_unknown';const value=b&255;
 if(value===102)return 'icon_battery_usb';if(value>100)return 'icon_battery_unknown';
 return 'icon_battery_'+(b&256?'charge_':'')+Math.round(value/10);
}
function condition(c){if(c===0)return '晴';if(c<3)return '多云';if(c===3)return '阴';if(c<50)return '雾';if(c<70)return '雨';if(c<80)return '雪';if(c<85)return '阵雨';if(c<90)return '阵雪';return '雷雨';}
function validPlace(p){return p&&typeof p.city==='string'&&Number.isFinite(p.latitude)&&Math.abs(p.latitude)<=90&&Number.isFinite(p.longitude)&&Math.abs(p.longitude)<=180;}
// ISO daily solar times are local to the API's returned city offset.
// No fixed-hour day/night rule; stale/missing solar data falls back explicitly.
function solarData(d){
 const daily=d&&d.daily,offset=d&&d.utc_offset_seconds;
 if(!daily||!Array.isArray(daily.time)||!Number.isFinite(offset)||Math.abs(offset)>50400)return null;
 const array=k=>Array.isArray(daily[k])?daily[k].slice(0,16):[];
 return {utc_offset_seconds:offset,daily:{time:array('time'),sunrise:array('sunrise'),sunset:array('sunset'),daylight_duration:array('daylight_duration')}};
}
function daylight(now){
 const s=weather&&weather.solar;
 if(s&&s.daily&&Number.isFinite(s.utc_offset_seconds)&&Math.abs(s.utc_offset_seconds)<=50400&&now>=1704067200000){
  const local=new Date(now+s.utc_offset_seconds*1000).toISOString().slice(0,19),daily=s.daily;
  const i=Array.isArray(daily.time)?daily.time.indexOf(local.slice(0,10)):-1;
  if(i>=0){
   const rise=(daily.sunrise||[])[i],end=(daily.sunset||[])[i];
   const valid=t=>typeof t==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?$/.test(t)&&t.slice(0,10)===local.slice(0,10);
   const seconds=t=>t.length===16?t+':00':t;
   if(valid(rise)&&valid(end)&&rise<end)return {day:local>=seconds(rise)&&local<seconds(end)?1:0,source:'sunrise_sunset',sunrise:rise,sunset:end};
   const duration=(daily.daylight_duration||[])[i];
   if(duration===0||duration>=86399)return {day:duration===0?0:1,source:'polar',sunrise:null,sunset:null};
  }
 }
 return {day:weather&&weather.day===0?0:1,source:weather&&(weather.day===0||weather.day===1)?'weather_flag':'unavailable',sunrise:null,sunset:null};
}
function cancel(){if(pending)try{call(http,'CancelRequest',{RequestId:pending.id});}catch(_){}pending=null;}
function status(now){
 if(now<nextStatus)return;nextStatus=now+5000;
 let online=false;try{online=call(wifi,'GetGeneralState')==='Connected';}catch(_){}
 icon('status/network',online?'icon_wifi_on':'icon_wifi_off');
 try{const m=call(modes,'GetState');asleep=!!m.screen_asleep;icon('status/battery',batterySymbol(m.battery_status));}catch(_){}
 const city=(place.city||'上海').slice(0,4);text('status/weather/city',city);
 if(face===2){const size=city.length<=2?28:22,width=Math.max(58,city.length*size+2),left=Math.round((688-(width+134))/2);set('status/weather/city','fontSize',size);set('status/weather/city','width',width);set('status/weather/city','x',left);set('status/weather/symbol','x',left+width+6);set('status/weather/temperature','x',left+width+52);}
 text('status/weather/temperature',weather?weather.temperature.toFixed(0)+'°C':'--°C');weatherIcon(now);
 if(weather)text('status/weatherAge',(now-weather.received_at>1800000?'天气缓存已过期':online?'':'离线天气缓存'));
 else text('status/weatherAge',online?'正在获取天气':'请连接 Wi-Fi');
 if(pending&&now-pending.started>25000){cancel();nextFetch=now+60000;}
 if(face!==0&&online&&!pending&&now>=nextFetch){
  nextFetch=now+600000;
  try{const url='https://api.open-meteo.com/v1/forecast?latitude='+place.latitude+'&longitude='+place.longitude+'&current=temperature_2m,weather_code,is_day&daily=sunrise,sunset,daylight_duration&forecast_days=3&timezone=auto';
   pending={id:call(http,'RequestAsync',{Request:{url,method:'Get',timeout_ms:15000,headers:{},body:''}}),started:now};
  }catch(_){nextFetch=now+60000;}
 }
}
function extraTick(){
 if(Date.now()<touchUntil)return; // Prioritize touch delivery over cat-frame decoding.
 if(paused)return;const now=Date.now();status(now);if(asleep){finish();second=-1;shown=null;return;}if(face===0){tick();return;}
 const d=new Date(now+8*3600000),valid=now>=1704067200000;
 text('status/date',valid?(d.getUTCMonth()+1)+'月'+d.getUTCDate()+'日  周'+'日一二三四五六'[d.getUTCDay()]:'等待校时');
 if(face===1){
  const sec=Math.floor(now/1000);if(sec===lastSecond)return;lastSecond=sec;
  const h=d.getUTCHours()%12,m=d.getUTCMinutes(),v=d.getUTCSeconds();
  const points=(angle,length,tail)=>{const a=angle*Math.PI/180;return JSON.stringify([{x:Math.round(170-tail*Math.sin(a)),y:Math.round(170+tail*Math.cos(a))},{x:Math.round(170+length*Math.sin(a)),y:Math.round(170-length*Math.cos(a))}]);};
  if(valid){call(gui,'SetBindings',{Updates:[['hour',h*30+m*.5+v/120,93,10],['minute',m*6+v*.1,133,10],['second',v*6,145,20]].map(a=>({Path:'/main/analog/'+a[0],Key:'points',Value:points(a[1],a[2],a[3])}))});}
 }else{
  if(flips.length&&now-started>=360)finish();tick();weatherIcon(now);
  const step=Math.floor(now/180),phase=step%8,pose=phase===4&&Math.floor(step/8)%4!==3?3:phase;
  const scene=daylight(now).day?'day':'night';
  if(pose!==pawFrame||scene!==catScene){
   const changed=scene!==catScene,begin=Date.now();
   try{if(changed)icon('companion/scene','cat_background_'+scene);call(gui,'SetViewSrc',{Path:'/main/companion/motion',Src:'cat_'+scene+'_'+pose});pawFrame=pose;catScene=scene;catUpdates++;catMaxMs=Math.max(catMaxMs,Date.now()-begin);catError='';}
   catch(e){catError=String(e);}
   if(changed||(!catReported&&catUpdates>=8)){catReported=catUpdates>=8;record();}
  }
 }
}
function select(next,persist){
 finish();face=(next+3)%3;cache={};lastSecond=-1;pawFrame=-1;second=-1;shown=null;nextStatus=0;
 for(const [id,i] of [['flip',0],['analog',1],['companion',2]])set(id,'hidden',face!==i);
 set('status','hidden',face===0);set('status/date','y',face===1?410:77);
 for(const [key,value] of [['x',face===1?80:32],['width',face===1?320:205],['fontSize',face===1?19:28]])set('status/date',key,value);
 set('status/weather','y',face===1?437:77);set('status/weatherAge','hidden',true);
 for(const [id,x,width] of face===2?[['city',248,58],['temperature',358,82]]:[['city',143,70],['temperature',262,80]]){
  set('status/weather/'+id,'x',x);set('status/weather/'+id,'width',width);set('status/weather/'+id,'fontSize',face===2?28:20);
 }
 set('status/weather/symbol','x',face===2?312:216);
 for(let i=0;i<3;i++)set('pager/page'+i,'color',i===face?'#d7e3f9':'#536078');
 if(face===0)cancel();extraTick();
 if(persist)try{call(storage,'FSWriteText',{Path:'/littlefs/clock-face.json',Data:JSON.stringify({face})});}catch(_){}
 record();
}
globalThis.brookesia_app={
 on_start(){
  gui=brookesia.start_service('SystemGui');timer=brookesia.start_service('SystemTimer');storage=brookesia.start_service('Storage');brookesia.start_service('SNTP');
  wifi=brookesia.start_service('Wifi');http=brookesia.start_service('Http');modes=brookesia.start_service('DeviceModes');
  for(const e of ['RequestCompleted','RequestFailed','RequestCanceled'])brookesia.subscribe_event(http,e);
  for(const a of ['facePress','faceMove','faceGesture','faceRelease','faceCancel'])call(gui,'SubscribeAction',{Action:a});
  catScene='';catUpdates=0;catMaxMs=0;catError='';catReported=false;asleep=false;iconState={};frames=0;reported=false;nativeIds=[];nativeFlips=0;
  const settings=read('/littlefs/weather-settings.json'),old=read('/littlefs/weather-cache.json'),own=read('/littlefs/clock-weather.json');
  if(old&&old.mode===(settings&&settings.mode==='auto'?'auto':'shanghai')&&validPlace(old.location)){place=old.location;const c=old.data&&old.data.current;if(c&&Number.isFinite(c.temperature_2m)&&Number.isInteger(c.weather_code))weather={temperature:c.temperature_2m,code:c.weather_code,day:c.is_day,solar:solarData(old.data),received_at:old.received_at||0};}
  if(own&&validPlace(own.place)&&own.place.latitude===place.latitude&&own.place.longitude===place.longitude&&own.weather&&Number.isFinite(own.weather.temperature)&&Number.isInteger(own.weather.code)&&(!weather||own.weather.received_at>weather.received_at)){place=own.place;weather=own.weather;}
  nextFetch=weather&&weather.solar?weather.received_at+600000:0;const pref=read('/littlefs/clock-face.json');paused=false;select(pref&&Number.isInteger(pref.face)&&pref.face>=0&&pref.face<3?pref.face:0,false);call(timer,'StartPeriodic',{Name:'clock',IntervalMs:180});return true;
 },
 on_action(name,path,payload){
  if(paused||asleep){press=null;touchUntil=0;return true;}
  if(name==='faceCancel'){press=null;touchUntil=0;return true;}
  let p;try{p=typeof payload==='string'?JSON.parse(payload):payload;}catch(_){press=null;return true;}
  if(name==='faceGesture'){
   if(p&&press&&(p.direction==='left'||p.direction==='right')&&Date.now()-lastSwipe>=180){press=null;lastSwipe=Date.now();select(face+(p.direction==='left'?1:-1),true);}
   else if(p&&(p.direction==='up'||p.direction==='down'))press=null;
   return true;
  }
  if(!p||!Number.isFinite(p.x)||!Number.isFinite(p.y))return true;
  if(name==='facePress'){press={x:p.x,y:p.y};touchUntil=Date.now()+1500;return true;}
  if(name==='faceMove')touchUntil=Date.now()+1500;
  if(name==='faceRelease')touchUntil=0;
  if(name==='faceMove'||name==='faceRelease')swipePoint(p,name==='faceRelease');
  return true;
 },
 on_event(service,event,payload){
  if(paused||service!=='Http'||!pending)return true;
  try{const v=JSON.parse(payload);if(v.RequestId!==pending.id)return true;pending=null;const r=v.Response||{};if(r.status_code!==200||r.error!=='Ok')throw Error('weather');const d=JSON.parse(r.body),c=d.current;if(!c||!Number.isFinite(c.temperature_2m)||!Number.isInteger(c.weather_code)||c.temperature_2m< -100||c.temperature_2m>70)throw Error('weather');weather={temperature:c.temperature_2m,code:c.weather_code,day:c.is_day,solar:solarData(d),received_at:Date.now()};call(storage,'FSWriteText',{Path:'/littlefs/clock-weather.json',Data:JSON.stringify({place,weather})});nextStatus=0;extraTick();}catch(_){pending=null;nextFetch=Date.now()+60000;}return true;
 },
 on_timer(id,name){if(name==='flip')animate();else extraTick();return true;},
 on_pause(){finish();paused=true;press=null;touchUntil=0;stopFx();cancel();return true;},
 on_resume(){paused=false;reported=false;select(face,false);return true;},
 on_stop(){paused=true;press=null;touchUntil=0;stopFx();stopNative();cancel();flips=[];return true;}
};
})();
