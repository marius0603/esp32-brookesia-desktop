(function () {
'use strict';
// Device-side Wi-Fi -> verified HTTPS -> GUI. No computer weather bridge.
const CITIES = {
  shanghai: {city:'上海', latitude:31.2304, longitude:121.4737, origin:'手动选择'},
  qingdao: {city:'青岛', latitude:36.0671, longitude:120.3826, origin:'手动选择'}
};
const CACHE = '/littlefs/weather-cache.json', SETTINGS = '/littlefs/weather-settings.json';
const STATE = '/littlefs/weather-state.json', REFRESH_MS = 10*60*1000, STALE_MS = 30*60*1000;
const RETRY_DELAYS = [10000,30000];
// Asset generator reads this JSON-compatible object to render matching RGB565 tiles.
const SKY_PALETTES = {
  "idle":["#081421","#142b43"], "clear_day":["#70b8ec","#d1ebfa"], "clear_night":["#080e24","#122b43"],
  "cloudy_day":["#91afc6","#d7e3eb"], "cloudy_night":["#122030","#060e1c"],
  "rain_day":["#749bb5","#b7ccd9"], "rain_night":["#101f34","#050c18"],
  "storm_day":["#8199ad","#b0c3d2"], "storm_night":["#10182a","#050a13"],
  "snow_day":["#a5cbe7","#e3f1fa"], "snow_night":["#162d44","#081629"],
  "fog_day":["#a5b9c5","#d8e3e8"], "fog_night":["#202e3b","#0d1723"]
};
let gui, storage, http, wifi, timer, modes, core;
let hasCompact = false, compact = false;
let compactKey = '';
let screenAsleep=false, fxProbe=null, themedBackground=false;
let mode = 'shanghai', location = CITIES.shanghai, data = null, receivedAt = 0;
let connected = false, paused = false, pending = null, nextFetch = 0, failures = 0;
let lastRequest = 0, error = '', status = '未联网', rendered = {};
let fxDay=1, fxSky=null;
let fxScene='', fxTimer=0, tickTimer=0, fxLastTick=0, fxElapsed=0, fxInterval=250, fxFrames=0, fxError='', fxValues={};

const desktopColors = {
  background: '${color.bg.base}', sky: '${color.bg.overlay}', card: '${color.surface.base}', raised: '${color.surface.raised}',
  edge: '${color.border.default}', mutedEdge: '${color.border.muted}',
  text: '${color.text.default}', muted: '${color.text.muted}', accent: '${color.primary.fill}'
};

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
    '&hourly=temperature_2m,weather_code,is_day&daily=sunrise,sunset,daylight_duration&forecast_days=3&forecast_hours=25&timezone=auto';
}
// API ISO times use the returned fixed city offset, never the device TZ.
function cityTime(value) {
  const offset=value.utc_offset_seconds,now=Date.now();
  if(Number.isFinite(offset) && Math.abs(offset)<=86400 && now>=1704067200000)
    return new Date(now+offset*1000).toISOString().slice(0,19);
  return value.current.time;
}
function daylightAt(value,localTime,fallback) {
  const daily=value.daily;
  if(daily && Array.isArray(daily.time)){
    const i=daily.time.indexOf(localTime.slice(0,10));
    if(i>=0){
      const rise=daily.sunrise && daily.sunrise[i],set=daily.sunset && daily.sunset[i];
      const valid=t=>typeof t==='string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?$/.test(t) && t.slice(0,10)===localTime.slice(0,10);
      if(valid(rise)&&valid(set)&&rise<set){
        const seconds=t=>t.length===16?t+':00':t;
        return {day:seconds(localTime)>=seconds(rise)&&seconds(localTime)<seconds(set)?1:0,source:'sunrise_sunset',sunrise:rise,sunset:set};
      }
      const duration=daily.daylight_duration && daily.daylight_duration[i];
      if(duration===0 || duration>=86399)return {day:duration===0?0:1,source:'polar',sunrise:null,sunset:null};
    }
  }
  return {day:fallback===0?0:1,source:'weather_flag',sunrise:null,sunset:null};
}
function daylightNow(){return data?daylightAt(data,cityTime(data),data.current.is_day):{day:1,source:'unavailable',sunrise:null,sunset:null};}
function hours24(value) {
  const h=value.hourly, out=[];
  for (let i=0;i<h.time.length && out.length<24;i++) {
    if (h.time[i]>=value.current.time) out.push({time:h.time[i],temperature:h.temperature_2m[i],code:h.weather_code[i],day:daylightAt(value,h.time[i],h.is_day[i]).day});
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

function showCompact(show) {
  if (!hasCompact) return;
  compact = show;
  compactKey = '';
  rendered = {};
  stopFx();
  fxScene = '';
  updateBindings([
    binding('/main/content', 'hidden', show),
    binding('/main/backdrop', 'hidden', show),
    binding('/main/sky_texture', 'hidden', show),
    binding('/main/compact', 'hidden', !show),
    binding('/main/compact_return', 'hidden', show)
  ]);
}

function renderCompact() {
  const path = '/main/compact';
  const stale = !!data && (Date.now() - receivedAt >= STALE_MS || Date.now() < receivedAt);
  const cached = !!data && (!connected || stale || !!error);
  const key = JSON.stringify([receivedAt, location.city, status, cached]);
  if (key === compactKey) return;
  const updates = [
    binding(path + '/city', 'selected', mode === 'qingdao' ? 1 : 0),
    binding(path + '/source', 'text', cached ? '缓存天气' : status === '已更新' ? 'Open-Meteo' : status),
    binding(path + '/data/forecast', 'hidden', !data),
    binding(path + '/data/hero/icon', 'hidden', !data)
  ];
  if (data) {
    const current = data.current;
    const day = daylightNow().day;
    const hours = hours24(data);
    const temps = hours.map(hour => hour.temperature).filter(Number.isFinite);
    const forecast = path + '/data/forecast';
    const hero = path + '/data/hero';
    const samples = [0, 2, 4, 6, 8, 10].map(index => hours[index]);
    const sampleTemps = samples.map(hour => hour.temperature).filter(Number.isFinite);
    updates.push(
      binding(hero + '/temperature', 'text', num(current.temperature_2m) + '°'),
      binding(hero + '/condition', 'text', condition(current.weather_code, day)),
      binding(hero + '/range', 'text', temps.length ? '未来 24 小时  ' + num(Math.min(...temps)) + '° – ' + num(Math.max(...temps)) + '°' : '')
    );
    const low = Math.min(...sampleTemps);
    const span = Math.max(2, Math.max(...sampleTemps) - low);
    const points = [];
    samples.forEach((hour, index) => {
      const valid = Number.isFinite(hour.temperature);
      const y = valid ? 72 - Math.round((hour.temperature - low) * 51 / span) : 72;
      if (valid) points.push({x: 45 + 67 * index, y});
      updates.push(binding(forecast + '/temp' + index, 'text', valid ? num(hour.temperature) + '°' : ''),
        binding(forecast + '/temp' + index, 'point_y', 47 + y - 23),
        binding(forecast + '/hour' + index, 'text', index === 0 ? '现在' : hour.time.slice(11, 16)));
    });
    updates.push(binding(forecast + '/trace', 'points', JSON.stringify(points)));
    call(gui, 'SetViewSrc', {Path: hero + '/icon', Src: iconFor(current.weather_code, day)});
  } else {
    updates.push(
      binding(path + '/data/hero/temperature', 'text', '--°'),
      binding(path + '/data/hero/condition', 'text', status),
      binding(path + '/data/hero/range', 'text', '')
    );
  }
  for (let offset = 0; offset < updates.length; offset += 16) updateBindings(updates.slice(offset, offset + 16));
  compactKey = key;
}
function applyScene() {
  if (paused) return;
  if(screenAsleep){stopFx();return;}
  const solar=daylightNow(),day=solar.day,code=data?data.current.weather_code:0;
  const scene=data?sceneFor(code,day):'idle';
  if (scene===fxScene && day===fxDay && (scene==='idle' || fxTimer)) return;
  stopFx();
  const skyName=SKY_PALETTES[scene]?scene:scene+(day?'_day':'_night');
  const c=SKY_PALETTES[skyName] || SKY_PALETTES.idle, rain=scene==='rain'||scene==='storm';
  const clouds=scene.indexOf('cloudy')===0 || rain || scene==='snow';
  const celestial=scene!=='idle' && scene!=='fog' && scene!=='storm' && code!==3;
  const stars=!day && (scene==='clear_night' || (scene==='cloudy_night' && code!==3));
  const light=day && scene!=='idle';
  const darkInk=light && !themedBackground;
  const updates=[binding('/main','sky',themedBackground?desktopColors.background:c[0]),
    binding('/main','sky_bottom',themedBackground?desktopColors.sky:c[1]),
    binding('/main/backdrop/shade','opacity',themedBackground?0:light?12:45),
    binding('/main/backdrop/rain','opacity',light?140:255),
    binding('/main/content/temperature','ink',themedBackground?desktopColors.accent:darkInk?'#102f4d':'#ffffff'),
    binding('/main/content/humidity','ink',themedBackground?desktopColors.muted:darkInk?'#183c55':'#c6e5ef'),
    binding('/main/content/condition','ink',themedBackground?desktopColors.text:darkInk?'#183c55':'#ffda83'),
    binding('/main/backdrop/rain','hidden',!rain),binding('/main/backdrop/sun','hidden',!(day && celestial)),
    binding('/main/backdrop/moon','hidden',!(!day && celestial)),
    binding('/main/backdrop/stars','hidden',!stars),
    binding('/main/backdrop/clouds','hidden',!clouds),
    binding('/main/backdrop/fog','hidden',scene!=='fog'),binding('/main/backdrop/snow','hidden',scene!=='snow')];
  for (let i=0;i<4;i++) updates.push(binding('/main/backdrop/drop'+i,'hidden',!rain));
  try {
    try {
      const skySrc='sky_'+(SKY_PALETTES[skyName]?skyName:'idle');
      call(gui,'SetViewSrc',{Path:'/main/sky_texture',Src:skySrc});
      updates.push(binding('/main/sky_texture','hidden',false),
        binding('/main/sky_texture','opacity',themedBackground?16:255));
      fxSky=skySrc;
    } catch (_) {
      // Keep the color fallback and the animation if a tile is unavailable.
      updates.push(binding('/main/sky_texture','hidden',true));
      fxSky=null;
    }
    updateBindings(updates); fxScene=scene;fxDay=day; fxLastTick=Date.now(); fxElapsed=0; fxFrames=0; fxError='';fxValues={};fxProbe=null;
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
  }
  if (fxScene.indexOf('cloudy')===0 || fxScene==='rain' || fxScene==='storm' || fxScene==='snow') {
    add('clouds/c0','x',310+42*Math.sin(elapsed/2.5));add('clouds/c0','y',74+9*Math.sin(elapsed/3));
    add('clouds/c1','x',282+34*Math.sin(elapsed/3+1.8));add('clouds/c1','y',119+7*Math.sin(elapsed/4+1));
  }
  if (fxDay===1 && fxScene!=='idle' && fxScene!=='fog' && fxScene!=='storm') {
    add('sun','opacity',205+50*Math.sin(elapsed/1.8));add('sun','y',64+10*Math.sin(elapsed/2.5));
  } else if (fxDay===0 && fxScene!=='idle' && fxScene!=='fog' && fxScene!=='storm') {
    add('moon','opacity',210+45*Math.sin(elapsed/2));add('moon','y',70+10*Math.sin(elapsed/2.5));
  }
  if (fxScene==='fog') {
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
  write(STATE,{version:4,background:fxScene,sky_texture:fxSky,day_phase:fxDay?'day':'night',solar:daylightNow(),screen_asleep:screenAsleep,fx_probe:fxProbe,fx_frames:fxFrames,fx_error:fxError,fx_active:!!fxTimer,fx_interval_ms:fxInterval,paused:paused,hourly_count:data?hours24(data).length:0,status:status,error:error,connected:connected,mode:mode,location:location,
    pending:pending?pending.kind:null,last_weather_request_id:lastRequest,
    received_at:receivedAt,source_time:data?data.current.time:null,
    temperature:data?data.current.temperature_2m:null,ui_updated:!paused && !!data});
}
function hourlyTheme(day) {
  if (themedBackground) {
    return {background:day===0?desktopColors.card:desktopColors.raised,
      edge:day===0?desktopColors.mutedEdge:desktopColors.edge,
      ink:desktopColors.text, muted:desktopColors.muted, temperature:desktopColors.accent};
  }
  return day===0?{background:'#102b42',edge:'#55728b',ink:'#e6effa',muted:'#abc8de'}:
    {background:'#fff5e5',edge:'#7693aa',ink:'#183c55',muted:'#35566e'};
}
function syncHourlyThemes(hours) {
  if(paused)return;
  const updates=[],changed=[];
  for(let i=0;i<hours.length;i++){
    const day=hours[i].day===0?0:1,key='hourTheme'+i;
    if(rendered[key]===day)continue;
    const t=hourlyTheme(day),path='/main/content/hourly/h'+i;
    updates.push(binding(path,'card_bg',t.background),binding(path,'card_edge',t.edge),
      binding(path+'/time','ink',t.ink),binding(path+'/temperature','ink',t.temperature || t.ink),
      binding(path+'/condition','muted_ink',t.muted));
    changed.push([key,day]);
  }
  // Keep each request bounded, and repaint only cards whose daylight changes.
  for(let i=0;i<updates.length;i+=20)updateBindings(updates.slice(i,i+20));
  for(const item of changed)rendered[item[0]]=item[1];
}
function render() {
  if (compact) {
    if (!paused) renderCompact();
    return;
  }
  applyScene();
  const stale=!!data && (Date.now()-receivedAt>=STALE_MS || Date.now()<receivedAt);
  const networkLabel=status==='已更新'?(stale?'数据过期':'Open-Meteo'):status+(stale?' · 数据过期':'');
  text('source',networkLabel+' · 刷新');
  if (!data) { text('condition',status); return; }
  const c=data.current;
  text('temperature',num(c.temperature_2m,1)+'°C');
  text('humidity','湿度 '+num(c.relative_humidity_2m)+'%');
  text('condition',(!connected || error || stale?'缓存 · ':'')+condition(c.weather_code,daylightNow().day));
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
  syncHourlyThemes(hours);
}
function setStatus(value) { status=value; render(); persistState(); }
function cancelPending() {
  const request = pending;
  pending = null;
  if (request) { try { call(http, 'CancelRequest', {RequestId:request.id}); } catch (_) {} }
}
function request(kind, url) {
  const id = call(http,'RequestAsync',{Request:{url:url,method:'Get',timeout_ms:15000,
    max_response_size:8192,retry_count:0,tls_verify:'Verify',use_crt_bundle:true,
    headers:{Accept:'application/json','User-Agent':'BrookesiaWeather/0.2'}}});
  pending={id:id,kind:kind,started:Date.now()};
  setStatus('连接中');
}
function requestWeather() { request('weather',forecastUrl(location)); }
function beginFetch() {
  if (pending || !connected || failures>RETRY_DELAYS.length) return;
  try {
    requestWeather();
  } catch (e) { failed(String(e)); }
}
function failed(message) {
  pending=null; error=String(message).slice(0,160); failures++;
  nextFetch=failures<=RETRY_DELAYS.length?Date.now()+RETRY_DELAYS[failures-1]:Infinity;
  setStatus('服务不可用');
}
function handleResponse(items) {
  if (!pending || items.RequestId !== pending.id) return;
  const id=pending.id, response=items.Response || {};
  pending=null;
  const ok=response.status_code===200 && response.error==='Ok';
  if (!ok) { failed('HTTP '+(response.status_code||0)+' '+(response.error||'RequestFailed')); return; }
  try {
    const value=validateWeather(JSON.parse(response.body));
    data=value; receivedAt=Date.now(); lastRequest=id; failures=0; error=''; nextFetch=receivedAt+REFRESH_MS;
    write(cachePath(), {version:2, mode, location, received_at:receivedAt, data});
    setStatus('已更新');
  } catch(e) { failed(String(e)); }
}
function tick() {
  try {
    if(modes){try{const state=call(modes,'GetState'),asleep=!!(state && state.screen_asleep);if(asleep!==screenAsleep){screenAsleep=asleep;applyScene();persistState();}}catch(_){}}
    if(screenAsleep)stopFx();
    let link;
    try {link=call(wifi,'GetGeneralState',{});} catch (_) {link=null;}
    if (link!=='Connected') {
      const offlineStatus=link===null?'服务不可用':link==='Connecting'?'连接中':'未联网';
      if (connected || status!==offlineStatus) { connected=false; cancelPending(); setStatus(offlineStatus); }
      render();return;
    }
    if (!connected) { connected=true; nextFetch=0; failures=0; }
    if (pending && Date.now()-pending.started>25000) { cancelPending(); failed('请求超时'); }
    if (!pending && Date.now()>=nextFetch) beginFetch();
    render();
  } catch(e) { failed(String(e)); }
}
function cachePath() {
  return mode === 'qingdao' ? '/littlefs/weather-cache-qingdao.json' : CACHE;
}
function loadCityCache() {
  location = CITIES[mode];
  data = null;
  receivedAt = 0;
  const cache = read(cachePath());
  if (!cache || cache.version !== 2 || cache.mode !== mode) return;
  try {
    data = validateWeather(cache.data);
    receivedAt = cache.received_at || 0;
  } catch (_) {}
}
function selectCity(index) {
  if (index !== 0 && index !== 1) return;
  const next = index === 1 ? 'qingdao' : 'shanghai';
  if (next === mode) return;
  try {
    const previous = read(SETTINGS) || {};
    call(storage, 'FSWriteText', {Path:SETTINGS, Data:JSON.stringify({...previous, mode:next})});
  } catch (_) {
    compactKey = '';
    setStatus('无法保存城市');
    return;
  }
  cancelPending();
  mode = next;
  loadCityCache();
  failures = 0;
  error = '';
  nextFetch = 0;
  lastRequest = 0;
  compactKey = '';
  rendered = {};
  setStatus(connected ? '正在更新' : '未联网');
  tick();
}
globalThis.brookesia_app = {
  on_start() {
    themedBackground=false;
    try{
      modes=brookesia.start_service('DeviceModes');
      themedBackground=Boolean(call(modes,'GetState')?.app_background_follows_theme);
    }catch(_){}
    gui=brookesia.start_service('SystemGui'); storage=brookesia.start_service('Storage');
    wifi=brookesia.start_service('Wifi'); http=brookesia.start_service('Http'); timer=brookesia.start_service('SystemTimer');
    for (const event of ['RequestCompleted','RequestFailed','RequestCanceled']) brookesia.subscribe_event(http,event);
    brookesia.subscribe_event(wifi,'GeneralEventHappened');
    call(gui,'SubscribeAction',{Action:'refresh'});
    try { hasCompact = Boolean(call(gui, 'GetViewFrame', {Path: '/main/compact'})?.width); } catch (_) { hasCompact = false; }
    if (hasCompact) {
      core = brookesia.start_service('SystemCore');
      for (const action of ['compact.back', 'compact.details', 'compact.overview', 'compact.refresh', 'compact.city']) call(gui, 'SubscribeAction', {Action: action});
      showCompact(true);
    }
    const settings = read(SETTINGS);
    mode = settings?.mode === 'qingdao' ? 'qingdao' : 'shanghai';
    status = '未联网';
    loadCityCache();
    stopFx();stopTick();fxScene='';paused=false;rendered={};render();startTick();tick();return true;
  },
  on_action(name, path, payload) {
    if (name === 'compact.city' && !paused) {
      let selected;
      try { selected = JSON.parse(payload || '{}').selectedIndex; } catch (_) {}
      selectCity(selected);
      return true;
    }
    if((name==='refresh'||name==='compact.refresh')&&!paused&&!pending){failures=0;nextFetch=0;tick();}
    if (!paused && hasCompact) {
      if (name === 'compact.back') {
        const app = call(core, 'GetActiveApp');
        if (app?.manifest?.id === 'local.weather') call(core, 'RequestCloseApp', {AppId:app.app_id});
      } else if (name === 'compact.details' || name === 'compact.overview') {
        showCompact(name === 'compact.overview');
        render();
      }
    }
    return true;
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
  on_resume() { paused=false;failures=0;nextFetch=0;rendered={};fxScene='';compactKey='';render();startTick();tick();persistState();return true; },
  on_stop() { paused=true;stopFx();stopTick();cancelPending();persistState();return true; }
};

})();
