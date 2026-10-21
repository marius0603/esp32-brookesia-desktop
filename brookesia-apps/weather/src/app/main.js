(function () {
'use strict';
// Device-side Wi-Fi -> verified HTTPS -> GUI. No computer weather bridge.
const SHANGHAI = {city:'上海', latitude:31.2304, longitude:121.4737, origin:'默认城市'};
const CACHE = '/littlefs/weather-cache.json', SETTINGS = '/littlefs/weather-settings.json';
const STATE = '/littlefs/weather-state.json', REFRESH_MS = 10*60*1000, STALE_MS = 30*60*1000;
let gui, storage, http, wifi, timer, modes;
let screenAsleep=false, fxProbe=null;
let mode = 'shanghai', location = SHANGHAI, data = null, receivedAt = 0;
let connected = false, paused = false, pending = null, nextFetch = 0, failures = 0;
let lastRequest = 0, error = '', status = '等待联网', rendered = {};
let fxScene='', fxTimer=0, tickTimer=0, fxLastTick=0, fxElapsed=0, fxInterval=250, fxFrames=0, fxError='', fxValues={};

function call(handle, name, args) {
  const result = JSON.parse(brookesia.call_function(handle, name, JSON.stringify(args || {})));
  if (!result.success) throw new Error(result.error || name);
  return result.data;
}
function read(path) { try { return JSON.parse(call(storage,'FSReadText',{Path:path})); } catch (_) { return null; } }
function write(path, value) { try { call(storage,'FSWriteText',{Path:path,Data:JSON.stringify(value)}); } catch (_) {} }
function text(id, value) {
  value = String(value);
  if (paused || rendered[id] === value) return;
  call(gui,'SetText',{Path:'/main/content/'+id,Text:value}); rendered[id] = value;
}
function num(value, digits) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits || 0) : '--';
}
function condition(code, day) {
  const names = {0:day===0?'晴夜':'晴',1:'晴间多云',2:'多云',3:'阴',45:'雾',48:'雾凇',
    51:'小毛毛雨',53:'毛毛雨',55:'强毛毛雨',56:'冻毛毛雨',57:'强冻毛毛雨',61:'小雨',63:'中雨',65:'大雨',
    66:'冻雨',67:'强冻雨',71:'小雪',73:'中雪',75:'大雪',77:'米雪',80:'小阵雨',81:'阵雨',82:'强阵雨',
    85:'小阵雪',86:'强阵雪',95:'雷雨',96:'雷雨伴冰雹',97:'强雷雨',99:'强雷雨伴冰雹'};
  return names[code] || '天气未知';
}
function forecastUrl(place) {
  return 'https://api.open-meteo.com/v1/forecast?latitude='+place.latitude+'&longitude='+place.longitude+
    '&current=temperature_2m,relative_humidity_2m,is_day,weather_code'+
    '&hourly=temperature_2m,weather_code,is_day&forecast_hours=25&timezone=auto';
}
function hours24(value) {
  const h=value.hourly, out=[];
  for (let i=0;i<h.time.length && out.length<24;i++) {
    if (h.time[i]>=value.current.time) out.push({time:h.time[i],temperature:h.temperature_2m[i],code:h.weather_code[i],day:h.is_day[i]});
  }
  return out;
}
function validateWeather(value) {
  if (!value || value.error || !value.current || !value.hourly ||
      typeof value.current.temperature_2m !== 'number' || !Number.isFinite(value.current.temperature_2m) ||
      typeof value.current.time !== 'string' || !Array.isArray(value.hourly.time) ||
      !Array.isArray(value.hourly.temperature_2m) || !Array.isArray(value.hourly.weather_code) ||
      !Array.isArray(value.hourly.is_day) || hours24(value).length!==24) throw new Error('天气数据格式错误');
  return value;
}
function sceneFor(code,day) {
  if (code>=95 && code<=99) return 'storm';
  if ((code>=51 && code<=67) || (code>=80 && code<=82)) return 'rain';
  if ((code>=71 && code<=77) || code===85 || code===86) return 'snow';
  if (code===45 || code===48) return 'fog';
  if (code>=1 && code<=3) return day===0?'cloudy_night':'cloudy_day';
  return day===0?'clear_night':'clear_day';
}
function iconFor(code,day) {
  const scene=sceneFor(code,day);
  if (scene.indexOf('cloudy')===0) return 'wx_cloud';
  if (scene==='clear_day') return 'wx_sun';
  if (scene==='clear_night') return 'wx_moon';
  return 'wx_'+scene;
}
function updateBindings(updates) { call(gui,'SetBindings',{Updates:updates}); }
function binding(path,key,value) { return {Path:path,Key:key,Value:String(value)}; }
function stopFx() {
  if (fxTimer) { try { call(timer,'Stop',{TimerId:fxTimer}); } catch(_) {} fxTimer=0; }
}
function stopTick() {
  if (tickTimer) { try { call(timer,'Stop',{TimerId:tickTimer}); } catch(_) {} tickTimer=0; }
}
function startTick() {
  if (!tickTimer) tickTimer=call(timer,'StartPeriodic',{Name:'weather',IntervalMs:5000});
}
function applyScene() {
  if (paused) return;
  if(screenAsleep){stopFx();return;}
  const scene=data?sceneFor(data.current.weather_code,data.current.is_day):'idle';
  if (scene===fxScene && (scene==='idle' || fxTimer)) return;
  stopFx();
  const colors={idle:['#081421','#142b43'],clear_day:['#143953','#071925'],clear_night:['#080e24','#122b43'],
    cloudy_day:['#263c4e','#102130'],cloudy_night:['#122030','#060e1c'],rain:['#122d40','#081421'],
    storm:['#171f38','#08111e'],snow:['#2a435a','#122239'],fog:['#344651','#15242e']};
  const c=colors[scene] || colors.idle, rain=scene==='rain'||scene==='storm';
  const updates=[binding('/main','sky',c[0]),binding('/main','sky_bottom',c[1]),
    binding('/main/backdrop/rain','hidden',!rain),binding('/main/backdrop/sun','hidden',scene!=='clear_day'),
    binding('/main/backdrop/moon','hidden',scene!=='clear_night'),
    binding('/main/backdrop/stars','hidden',scene!=='clear_night' && scene!=='cloudy_night'),
    binding('/main/backdrop/clouds','hidden',scene.indexOf('cloudy')!==0),
    binding('/main/backdrop/fog','hidden',scene!=='fog'),binding('/main/backdrop/snow','hidden',scene!=='snow')];
  for (let i=0;i<4;i++) updates.push(binding('/main/backdrop/drop'+i,'hidden',!rain));
  try {
    updateBindings(updates); fxScene=scene; fxLastTick=Date.now(); fxElapsed=0; fxFrames=0; fxError='';fxValues={};fxProbe=null;
    fxInterval=rain?125:250;
    if (scene!=='idle') fxTimer=call(timer,'StartPeriodic',{Name:'weather_fx',IntervalMs:fxInterval});
  } catch(e) { fxError=String(e); }
}
function animateFx() {
  if (paused || !fxTimer) return;
  const now=Date.now(),delta=now-fxLastTick;fxLastTick=now;
  fxElapsed+=(delta>=0 && delta<=1000?delta:fxInterval)/1000;
  const elapsed=fxElapsed, updates=[];
  function add(path,key,value) {
    value=Math.round(value);const id=path+'/'+key;
    if(fxValues[id]!==value){updates.push(binding('/main/backdrop/'+path,key,value));fxValues[id]=value;}
  }
  if (fxScene==='rain'||fxScene==='storm') {
    const speeds=[12,18,10,16];
    for(let i=0;i<4;i++)add('drop'+i,'y',Math.floor((i*110+80+elapsed*speeds[i])%576)-48);
  } else if (fxScene.indexOf('cloudy')===0) {
    add('clouds/c0','x',310+42*Math.sin(elapsed/2.5));add('clouds/c0','y',74+9*Math.sin(elapsed/3));
    add('clouds/c1','x',282+34*Math.sin(elapsed/3+1.8));add('clouds/c1','y',119+7*Math.sin(elapsed/4+1));
  } else if (fxScene==='clear_day') {
    add('sun','opacity',205+50*Math.sin(elapsed/1.8));add('sun','y',64+10*Math.sin(elapsed/2.5));
  } else if (fxScene==='clear_night') {
    add('moon','opacity',210+45*Math.sin(elapsed/2));add('moon','y',70+10*Math.sin(elapsed/2.5));
  } else if (fxScene==='fog') {
    for(let i=0;i<4;i++){
      add('fog/f'+i,'x',-20+12*Math.sin(elapsed/7+i));add('fog/f'+i,'opacity',220+30*Math.sin(elapsed/5+i));
    }
  } else if (fxScene==='snow') {
    add('snow','x',6*Math.sin(elapsed/9));
    for(let i=0;i<20;i++)add('snow/s'+i,'y',((24+i*61)%450+elapsed*(8+i%5*2))%520-8);
  }
  if(fxScene==='clear_night' || fxScene==='cloudy_night'){
    for(let i=0;i<8;i++)add('stars/s'+i,'opacity',145+110*Math.sin(elapsed*2+i*1.7));
    const phase=elapsed%12;
    add('stars/shooting','opacity',phase<2?245:0);
    add('stars/shooting','x',250+phase*80);add('stars/shooting','y',26+phase*46);
  }
  try {
    if(updates.length)updateBindings(updates);fxFrames++;
    if(fxFrames===8 || fxFrames===40){
      const path=fxScene.indexOf('cloudy')===0?'clouds/c0':fxScene==='clear_night'?'moon':fxScene==='clear_day'?'sun':fxScene==='snow'?'snow/s0':fxScene==='fog'?'fog/f0':'drop0';
      try{fxProbe={path:path,frame:call(gui,'GetViewFrame',{Path:'/main/backdrop/'+path}),expected:fxValues[path+'/y'],tick:fxFrames};}catch(_){}
      persistState();
    }
  }
  catch(e) { fxError=String(e);stopFx();persistState(); }
}
function persistState() {
  write(STATE,{version:3,background:fxScene,screen_asleep:screenAsleep,fx_probe:fxProbe,fx_frames:fxFrames,fx_error:fxError,fx_active:!!fxTimer,fx_interval_ms:fxInterval,paused:paused,hourly_count:data?hours24(data).length:0,status:status,error:error,connected:connected,mode:mode,location:location,
    pending:pending?pending.kind:null,last_weather_request_id:lastRequest,
    received_at:receivedAt,source_time:data?data.current.time:null,
    temperature:data?data.current.temperature_2m:null,ui_updated:!paused && !!data});
}
function render() {
  applyScene();
  if (!data) { text('condition',status); return; }
  const c=data.current, stale=Date.now()-receivedAt>STALE_MS;
  text('temperature',num(c.temperature_2m,1)+'°C');
  text('humidity','湿度 '+num(c.relative_humidity_2m)+'%');
  text('condition',(!connected || error || stale?'缓存 · ':'')+condition(c.weather_code,c.is_day));
  const hours=hours24(data);
  for (let i=0;i<hours.length;i++) {
    const h=hours[i], path='hourly/h'+i;
    text(path+'/time',h.time.slice(11,16));
    text(path+'/temperature',num(h.temperature)+'°');
    text(path+'/condition',condition(h.code,h.day));
    const icon=iconFor(h.code,h.day), key='icon'+i;
    if (!paused && rendered[key]!==icon) {
      call(gui,'SetViewSrc',{Path:'/main/content/'+path+'/icon',Src:icon});rendered[key]=icon;
    }
  }
}
function setStatus(value) { status=value; render(); persistState(); }
function cancelPending() {
  if (pending) { try { call(http,'CancelRequest',{RequestId:pending.id}); } catch (_) {} }
  pending=null;
}
function request(kind, url) {
  const id = call(http,'RequestAsync',{Request:{url:url,method:'Get',timeout_ms:15000,
    max_response_size:8192,retry_count:0,tls_verify:'Verify',use_crt_bundle:true,
    headers:{Accept:'application/json','User-Agent':'BrookesiaWeather/0.2'}}});
  pending={id:id,kind:kind,started:Date.now()};
  setStatus(kind==='location'?'正在定位（网络出口）':data?'正在更新天气':'正在获取天气');
}
function requestWeather() { request('weather',forecastUrl(location)); }
function beginFetch() {
  if (pending || !connected) return;
  error='';
  try {
    if (mode==='auto') request('location','https://ipwho.is/?fields=success,message,city,latitude,longitude');
    else { location=SHANGHAI; requestWeather(); }
  } catch (e) { failed(String(e)); }
}
function failed(message) {
  pending=null; error=String(message).slice(0,160); failures++;
  nextFetch=Date.now()+Math.min(15*60*1000,60000*Math.pow(2,Math.min(failures-1,4)));
  setStatus(data?'更新失败，显示缓存':'获取失败，稍后重试');
}
function handleResponse(items) {
  if (!pending || items.RequestId !== pending.id) return;
  const kind=pending.kind, id=pending.id, response=items.Response || {};
  pending=null;
  const ok=response.status_code===200 && response.error==='Ok';
  if (kind==='location') {
    try {
      const place=ok?JSON.parse(response.body):null;
      if (!place || !place.success || typeof place.city!=='string' || !place.city ||
          !Number.isFinite(place.latitude) || Math.abs(place.latitude)>90 ||
          !Number.isFinite(place.longitude) || Math.abs(place.longitude)>180) throw new Error('定位失败');
      location={city:place.city,latitude:place.latitude,longitude:place.longitude,origin:'网络出口推测'};
    } catch (_) { location={city:SHANGHAI.city,latitude:SHANGHAI.latitude,longitude:SHANGHAI.longitude,origin:'定位失败，默认城市'}; }
    try { requestWeather(); } catch(e) { failed(String(e)); }
    return;
  }
  if (!ok) { failed('HTTP '+(response.status_code||0)+' '+(response.error||'RequestFailed')); return; }
  try {
    const value=validateWeather(JSON.parse(response.body));
    data=value; receivedAt=Date.now(); lastRequest=id; failures=0; error=''; nextFetch=receivedAt+REFRESH_MS;
    write(CACHE,{version:2,mode:mode,location:location,received_at:receivedAt,data:data});
    setStatus('已更新 · 每 10 分钟刷新');
  } catch(e) { failed(String(e)); }
}
function tick() {
  try {
    if(modes){try{const state=call(modes,'GetState'),asleep=!!(state && state.screen_asleep);if(asleep!==screenAsleep){screenAsleep=asleep;applyScene();persistState();}}catch(_){}}
    if(screenAsleep)stopFx();
    const online=call(wifi,'GetGeneralState',{})==='Connected';
    if (!online) {
      const offlineStatus=data?'网络断开，显示缓存':'等待 Wi-Fi 连接';
      if (connected || status!==offlineStatus) { connected=false; cancelPending(); setStatus(offlineStatus); }
      return;
    }
    if (!connected) { connected=true; nextFetch=0; }
    if (pending && Date.now()-pending.started>25000) { cancelPending(); failed('请求超时'); }
    if (!pending && Date.now()>=nextFetch) beginFetch();
    render();
  } catch(e) { failed(String(e)); }
}
globalThis.brookesia_app = {
  on_start() {
    try{modes=brookesia.start_service('DeviceModes');}catch(_){}
    gui=brookesia.start_service('SystemGui'); storage=brookesia.start_service('Storage');
    wifi=brookesia.start_service('Wifi'); http=brookesia.start_service('Http'); timer=brookesia.start_service('SystemTimer');
    for (const event of ['RequestCompleted','RequestFailed','RequestCanceled']) brookesia.subscribe_event(http,event);
    brookesia.subscribe_event(wifi,'GeneralEventHappened');
    const settings=read(SETTINGS); if (settings && settings.mode==='auto') mode='auto';
    const cache=read(CACHE);
    if (cache && cache.version===2 && cache.mode===mode) {
      try { data=validateWeather(cache.data); location=cache.location || SHANGHAI; receivedAt=cache.received_at || 0; status='显示上次天气'; } catch (_) {}
    }
    stopFx();stopTick();fxScene='';paused=false;rendered={};render();startTick();tick();return true;
  },
  on_timer(id,name) { if(paused)return true;if (name==='weather_fx') animateFx(); else tick(); return true; },
  on_event(service,event,json) {
    if(paused)return true;
    try {
      if (service==='Http') handleResponse(JSON.parse(json));
      else if (service==='Wifi') tick();
    } catch(e) { failed(String(e)); }
    return true;
  },
  on_pause() { paused=true;stopFx();stopTick();cancelPending();persistState();return true; },
  on_resume() { paused=false;rendered={};fxScene='';render();startTick();tick();persistState();return true; },
  on_stop() { paused=true;stopFx();stopTick();cancelPending();persistState();return true; }
};

})();
