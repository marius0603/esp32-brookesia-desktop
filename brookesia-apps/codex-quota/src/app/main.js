(function () {
'use strict';
let gui, storage, timer, lastBridge = 0, received = 0, rendered = 0, data = null, paused = false;
let fxTimer=0, frames=0, isStale=true, cache={}, primaryUsed=null, secondaryUsed=null;
let requestId='', requestAt=0, responded=false, fresh=false, hasExpired=false, quotaTimer=0;
const REQUEST_MS=60000, RESPONSE_MS=15000;
const PAC_TRAVEL=358;
// QUOTA_THEME_BEGIN
const themePalettes={"dark":{"root":"#090e17","card":"#151e2c","edge":"#2a3648","ink":"#edf2f8","muted":"#a6b4c7","track":"#0c1420","gold":"#ffd166","mint":"#71ddc9","pill":"#172a28","status":"#91dfbb"},"light":{"root":"#f5eddf","card":"#fffaf2","edge":"#dfd0b7","ink":"#453b31","muted":"#7d6b58","track":"#f0e5d2","gold":"#a86c12","mint":"#197e70","pill":"#e1eddb","status":"#35704e"}};
const themeNodes=[["/main","themebgColor","root"],["/main/sync","themebgColor","pill"],["/main/sync/status","themetextColor","status"],["/main/card_primary","themebgColor","card"],["/main/card_primary","themeborderColor","edge"],["/main/card_primary/label_primary","themetextColor","ink"],["/main/card_primary/primary","themetextColor","gold"],["/main/card_primary/unit_primary","themetextColor","gold"],["/main/card_primary/divider","themebgColor","edge"],["/main/card_primary/clock","themeborderColor","muted"],["/main/card_primary/clock/hour","themebgColor","muted"],["/main/card_primary/clock/minute","themebgColor","muted"],["/main/card_primary/days_primary","themetextColor","muted"],["/main/card_primary/reset_primary","themetextColor","ink"],["/main/card_primary/track_primary","themebgColor","track"],["/main/card_primary/track_primary/d0","themebgColor","gold"],["/main/card_primary/track_primary/d1","themebgColor","gold"],["/main/card_primary/track_primary/d2","themebgColor","gold"],["/main/card_primary/track_primary/d3","themebgColor","gold"],["/main/card_primary/track_primary/d4","themebgColor","gold"],["/main/card_primary/track_primary/d5","themebgColor","gold"],["/main/card_primary/track_primary/d6","themebgColor","gold"],["/main/card_primary/track_primary/d7","themebgColor","gold"],["/main/card_primary/track_primary/d8","themebgColor","gold"],["/main/card_primary/track_primary/d9","themebgColor","gold"],["/main/card_primary/track_primary/d10","themebgColor","gold"],["/main/card_primary/track_primary/d11","themebgColor","gold"],["/main/card_primary/track_primary/d12","themebgColor","gold"],["/main/card_primary/track_primary/d13","themebgColor","gold"],["/main/card_primary/track_primary/d14","themebgColor","gold"],["/main/card_primary/track_primary/d15","themebgColor","gold"],["/main/card_primary/track_primary/d16","themebgColor","gold"],["/main/card_primary/track_primary/d17","themebgColor","gold"],["/main/card_primary/track_primary/d18","themebgColor","gold"],["/main/card_primary/track_primary/d19","themebgColor","gold"],["/main/card_secondary","themebgColor","card"],["/main/card_secondary","themeborderColor","edge"],["/main/card_secondary/label_secondary","themetextColor","ink"],["/main/card_secondary/secondary","themetextColor","mint"],["/main/card_secondary/unit_secondary","themetextColor","mint"],["/main/card_secondary/divider","themebgColor","edge"],["/main/card_secondary/clock","themeborderColor","muted"],["/main/card_secondary/clock/hour","themebgColor","muted"],["/main/card_secondary/clock/minute","themebgColor","muted"],["/main/card_secondary/days_secondary","themetextColor","muted"],["/main/card_secondary/reset_secondary","themetextColor","ink"],["/main/card_secondary/track_secondary","themebgColor","track"],["/main/card_secondary/track_secondary/d0","themebgColor","mint"],["/main/card_secondary/track_secondary/d1","themebgColor","mint"],["/main/card_secondary/track_secondary/d2","themebgColor","mint"],["/main/card_secondary/track_secondary/d3","themebgColor","mint"],["/main/card_secondary/track_secondary/d4","themebgColor","mint"],["/main/card_secondary/track_secondary/d5","themebgColor","mint"],["/main/card_secondary/track_secondary/d6","themebgColor","mint"],["/main/card_secondary/track_secondary/d7","themebgColor","mint"],["/main/card_secondary/track_secondary/d8","themebgColor","mint"],["/main/card_secondary/track_secondary/d9","themebgColor","mint"],["/main/card_secondary/track_secondary/d10","themebgColor","mint"],["/main/card_secondary/track_secondary/d11","themebgColor","mint"],["/main/card_secondary/track_secondary/d12","themebgColor","mint"],["/main/card_secondary/track_secondary/d13","themebgColor","mint"],["/main/card_secondary/track_secondary/d14","themebgColor","mint"],["/main/card_secondary/track_secondary/d15","themebgColor","mint"],["/main/card_secondary/track_secondary/d16","themebgColor","mint"],["/main/card_secondary/track_secondary/d17","themebgColor","mint"],["/main/card_secondary/track_secondary/d18","themebgColor","mint"],["/main/card_secondary/track_secondary/d19","themebgColor","mint"]];
// QUOTA_THEME_END
let core, theme='dark';
function applyTheme(){
  try{if(!core)core=brookesia.start_service('SystemCore');theme=call(core,'GetEnvironment').theme_id==='dark'?'dark':'light';}catch(_){theme='dark';}
  call(gui,'SetBindings',{Updates:themeNodes.map(n=>binding(n[0],n[1],themePalettes[theme][n[2]]))});
}
function percent(id,used){
  const value=used===null?'--':String(Number((100-used).toFixed(1)));
  const size=value.length<=2?72:value.length<=3?52:value.length<=4?40:32;
  if(cache[id+'Size']!==size){call(gui,'SetBindings',{Updates:[binding(textPath(id),'fontSize',size)]});cache[id+'Size']=size;}
  const changed=cache[id]!==value;
  text(id,value);
  if(changed){
    let width=value.length*size*0.55;
    try{const frame=call(gui,'GetViewFrame',{Path:textPath(id)});if(frame&&frame.width>0)width=frame.width;}catch(_){}
    const x=Math.min(178,18+Math.ceil(width)+4);
    call(gui,'SetBindings',{Updates:[binding(textPath('unit_'+id),'x',x)]});cache[id+'UnitX']=x;
  }
}
function resetText(kind,at,now){
  const value=reset(at,now),split=value.indexOf(' ');
  text('days_'+kind,split>=0?value.slice(0,split):'');
  text('reset_'+kind,split>=0?value.slice(split+1):value);
  const size=/^\d{2}:/.test(split>=0?value.slice(split+1):value)?27:18;
  if(cache[kind+'TimeSize']!==size){call(gui,'SetBindings',{Updates:[binding(textPath('reset_'+kind),'fontSize',size)]});cache[kind+'TimeSize']=size;}
}
function requestQuota(active=true){
  if(active){requestId=String(Date.now())+'-'+String(Math.random()).slice(2);requestAt=Date.now();responded=false;}
  try{call(storage,'FSWriteText',{Path:'/littlefs/quota-request.json',Data:JSON.stringify({
    type:'quota_request',v:1,request_id:requestId,active:active
  })});}catch(_){} // No successful response still expires locally.
}
function trackPath(name){return '/main/card_'+name.replace('track_','')+'/'+name;}
function textPath(id){return id==='status'?'/main/sync/status':'/main/card_'+(id.endsWith('primary')?'primary':'secondary')+'/'+id;}
function call(handle, name, args) {
  const result = JSON.parse(brookesia.call_function(handle, name, JSON.stringify(args || {})));
  if (!result.success) throw new Error(result.error || name);
  return result.data;
}
function text(id, value) {
  value=String(value);if(cache[id]===value)return;
  call(gui,'SetText',{Path:textPath(id),Text:value});cache[id]=value;
}
function binding(path,key,value){return {Path:path,Key:key,Value:String(value)};}
function usedValue(window){return window && typeof window.used==='number' && Number.isFinite(window.used)?Math.max(0,Math.min(100,window.used)):null;}
function pellets(used){return Array.from({length:20},(_,i)=>used===null?0:Math.round(255*Math.max(0,Math.min(1,((i+1)*5-used)/5))));}
function pacX(used){return Math.round(PAC_TRAVEL*(used===null?0:used)/100);}
function showTrack(name,used){
  if(cache[name]===used)return;
  const updates=pellets(used).map((opacity,i)=>binding(trackPath(name)+'/d'+i,'opacity',opacity));
  updates.push(binding(trackPath(name)+'/pac','x',pacX(used)));
  call(gui,'SetBindings',{Updates:updates});cache[name]=used;
}
function persistState(){
  try{call(storage,'FSWriteText',{Path:'/littlefs/quota-ui-state.json',Data:JSON.stringify({version:2,
    sampled_at:data?data.sampled_at:0,primary_remaining:primaryUsed===null?null:100-primaryUsed,
    secondary_remaining:secondaryUsed===null?null:100-secondaryUsed,stale:isStale,animation_frames:frames,
    primary_x:pacX(primaryUsed),secondary_x:pacX(secondaryUsed),request_id:requestId,
    responded:responded,status:cache.status,theme:theme,ui_version:'0.2.5'})});}catch(_){}
}
function animate(){
  if(paused||!data||isStale||data.status!=='ok')return;
  const phase=['open','mid','closed','mid'][frames%4],updates=[];
  for(const item of [['track_primary',primaryUsed],['track_secondary',secondaryUsed]]){
    const name=item[0],used=item[1];if(used===null)continue;
    call(gui,'SetViewSrc',{Path:trackPath(name)+'/pac',Src:'pac_'+(used>=100?'closed':phase)});
    updates.push(binding(trackPath(name)+'/pac','x',Math.min(PAC_TRAVEL,pacX(used)+(used>=100?0:frames%2))));
  }
  if(updates.length)call(gui,'SetBindings',{Updates:updates});frames++;if(frames===8)persistState();
}
function startFx(){if(!fxTimer)fxTimer=call(timer,'StartPeriodic',{Name:'pacman',IntervalMs:240});}
function stopFx(){if(fxTimer){try{call(timer,'Stop',{TimerId:fxTimer});}catch(_){}fxTimer=0;}}
function reset(at, now) {
  if (!at) return '暂无重置时间';
  const seconds = Math.max(0, Math.floor(at-now));
  if (!seconds) return '等待同步';
  const days = Math.floor(seconds/86400), hours=Math.floor(seconds%86400/3600), minutes=Math.floor(seconds%3600/60);
  return (days ? days+'天 ' : '')+String(hours).padStart(2,'0')+':'+String(minutes).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');
}
function tick() {
  if (paused) return;
  if(!requestId || Date.now()<requestAt || Date.now()-requestAt>=REQUEST_MS)requestQuota();
  try {
    const packet = JSON.parse(call(storage,'FSReadText',{Path:'/littlefs/quota.json'}));
    if (packet.v !== 1 || packet.type !== 'quota' || !Array.isArray(packet.windows)) throw new Error('quota format');
    // Cached samples and unrelated responses never acknowledge a new request.
    if (!data || packet.request_id===requestId) {
      if(!data || packet.bridge_at!==lastBridge || packet.request_id!==data.request_id){lastBridge=packet.bridge_at||0;received=Date.now();}
      data=packet;
      if(packet.request_id===requestId){responded=true;fresh=packet.status==='ok' && !!packet.sampled_at;hasExpired=!fresh;}
    }
  } catch (_) { /* Keep the last valid sample when a file or transport is unavailable. */ }
  if(!responded && Date.now()-requestAt>=RESPONSE_MS){fresh=false;hasExpired=true;}
  const waiting=!responded && Date.now()-requestAt<RESPONSE_MS;
  const oldStatus=cache.status;
  isStale=!fresh;
  const status=data && data.request_id===requestId && data.status==='auth_required'?'需登录':
    waiting && !hasExpired?'等待同步':fresh?'已同步':'已过期';
  text('status',status);
  const dotColor=status==='已同步'?'#62e69b':status==='需登录'?'#ef8991':'#e9b65d';
  if(cache.dotColor!==dotColor){call(gui,'SetBindings',{Updates:[binding('/main/sync/dot','color',dotColor)]});cache.dotColor=dotColor;}
  if (!data){percent('primary',null);percent('secondary',null);if(oldStatus!==status)persistState();return;}
  const elapsed=(Date.now()-received)/1000, now=lastBridge+elapsed;
  const primary=data.windows.find(w=>w.kind==='primary')||data.windows[0];
  const secondary=data.windows.find(w=>w.kind==='secondary')||data.windows[1];
  primaryUsed=usedValue(primary);secondaryUsed=usedValue(secondary);
  percent('primary',primaryUsed);percent('secondary',secondaryUsed);
  showTrack('track_primary',primaryUsed);showTrack('track_secondary',secondaryUsed);
  resetText('primary',primary&&primary.reset_at,now);resetText('secondary',secondary&&secondary.reset_at,now);
  if (data.sampled_at !== rendered || oldStatus!==status) {
    console.log('Codex quota UI updated: '+data.sampled_at);
    rendered=data.sampled_at;
    persistState();
  }
}
globalThis.brookesia_app = {
  on_start() {
    gui=brookesia.start_service('SystemGui');
    storage=brookesia.start_service('Storage');
    timer=brookesia.start_service('SystemTimer');
    applyTheme();
    paused=false;
    if(!quotaTimer)quotaTimer=call(timer,'StartPeriodic',{Name:'quota',IntervalMs:1000});
    fresh=false;hasExpired=false;requestQuota();
    tick();
    startFx();
    return true;
  },
  on_timer(id,name) {if(name==='pacman')animate();else tick(); return true;},
  on_pause() {paused=true;requestQuota(false);stopFx();return true;},
  on_resume() {paused=false;cache={};applyTheme();fresh=false;requestQuota();tick();startFx();return true;},
  on_stop() {paused=true;requestQuota(false);stopFx();if(quotaTimer){try{call(timer,'Stop',{TimerId:quotaTimer});}catch(_){}quotaTimer=0;}return true;}
};
})();
