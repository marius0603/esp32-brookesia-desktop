const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),code=fs.readFileSync(path.join(root,'src/app/main.js'),'utf8');
// This pinned Brookesia stores handlers by schema position, discarding their
// legacy string names. A mismatch can silently route GetState to Resume.
const native=fs.readFileSync(path.resolve(root,'../../platform/super_s3_216/main/modules/radio/radio.cpp'),'utf8');
const schemaBlock=native.split('get_function_schemas()override')[1].split('get_function_handlers()override')[0];
const handlerBlock=native.split('get_function_handlers()override')[1].split('// A bounded read')[0];
const schemas=[...schemaBlock.matchAll(/\{"([A-Za-z]+)","/g)].map(m=>m[1]).filter(n=>n!=='Station'&&n!=='Minutes');
const handlers=[...handlerBlock.matchAll(/BROOKESIA_SERVICE_FUNC_HANDLER_\d\("([A-Za-z]+)"|\{"([A-Za-z]+)",\[/g)].map(m=>m[1]||m[2]);
assert.deepEqual(handlers,schemas,'Native handlers must match schema order');
const stations=JSON.parse(fs.readFileSync(path.join(root,'src/app/catalog.json'),'utf8')),layout=JSON.parse(fs.readFileSync(path.join(root,'src/res/screens/main.json'),'utf8'));
const views=new Map(),actions=new Set();function index(n,p=''){const k=p+'/'+n.id;views.set(k,n);for(const e of n.events||[]){assert(!actions.has(e.action),'Document action must be unique: '+e.action);actions.add(e.action);}if(n.imageProps)assert.match(n.imageProps.src,/^\$\{image\./);for(const c of n.children||[])index(c,k);}index(layout);
for(const p of ['/main/player/stations','/main/player/timer']){const n=views.get(p);assert(n.placement.y+n.placement.height<=466,'Bottom controls exceed touch safe area');}
let calls=[],texts={},bindings={},saved={},volume=40,quiet=false;
let state={station:'',active:false,paused:false,state:'Idle',sleep_active:false};
const brookesia={start_service:n=>n,call_function(h,n,json){
 const a=JSON.parse(json);calls.push({h,n,a});let data=null;
 if(h==='SystemGui'&&a.Path){assert(views.has(a.Path),'Unknown view '+a.Path);if(n==='SetBinding')assert(Object.values(views.get(a.Path).bindings||{}).includes(a.Key),'Unbound property '+a.Path+':'+a.Key);}
 if(n==='FSReadText'){
  if(a.Path.endsWith('/app/catalog.json'))data=JSON.stringify(stations);
  else if(saved[a.Path])data=saved[a.Path];else return JSON.stringify({success:false,error:'not found'});
 }
 if(n==='FSWriteText')saved[a.Path]=a.Data;
 if(h==='Radio'){
  if(n==='Play'){assert(stations.some(s=>s.id===a.Station));state={station:a.Station,active:true,paused:false,state:'Playing',sleep_active:false};}
  if(n==='Pause')state={...state,paused:true,state:'Paused'};
  if(n==='Resume')state={...state,paused:false,state:'Playing'};
  if(n==='Stop')state={...state,active:false,state:'Idle',sleep_active:false};
  if(n==='SetSleepTimer')state={...state,sleep_active:a.Minutes>0,sleep_remaining_seconds:a.Minutes*60};
 }
 if(n==='GetState')data=h==='DeviceModes'?{resume_volume:volume,do_not_disturb:quiet}:h==='Wifi'?'Connected':state;
 if(h==='Wifi'&&n==='GetGeneralState')data='Connected';
 if(n==='SetText')texts[a.Path]=a.Text;
 if(n==='SetBinding')bindings[a.Path+':'+a.Key]=a.Value;
 return JSON.stringify({success:true,data});
}};
const ctx=vm.createContext({brookesia});function start(){vm.runInContext(code,ctx);ctx.brookesia_app.on_start();}function action(n){ctx.brookesia_app.on_action(n);}
start();assert.equal(calls.filter(c=>c.h==='Radio'&&c.n==='Play').length,0,'Opening must be silent');
assert.equal(texts['/main/player/title'],'苏州儿童广播');
action('toggle');assert.equal(state.station,stations[0].id);action('toggle');assert.equal(state.paused,true);action('toggle');assert.equal(state.paused,false);
action('next');assert.equal(state.station,stations[1].id);action('previous');assert.equal(state.station,stations[0].id);
action('previous');assert.equal(state.station,stations[2].id,'Previous wraps within category');
action('favorite');assert.deepEqual(JSON.parse(saved['/littlefs/radio-settings.json']).favorites,[stations[2].id]);
action('stations');action('cat3');assert.equal(texts['/main/stations/row0/name'],'Story Quest');assert.equal(bindings['/main/stations/row1:hidden'],'true');action('row0');
action('timer');action('choice2');action('timerConfirm');assert.equal(state.sleep_remaining_seconds,1800);assert.equal(texts['/main/player/timer/label'],'30分钟');
volume=15;quiet=true;ctx.brookesia_app.on_timer();assert.equal(texts['/main/player/volume'],'音量 15% · 静音');
ctx.brookesia_app.on_pause();const before=calls.length;ctx.brookesia_app.on_timer();assert.equal(calls.length,before);ctx.brookesia_app.on_resume();
state={...state,active:false,state:'TimerEnded',sleep_active:false};ctx.brookesia_app.on_timer();assert.equal(texts['/main/player/status'],'定时结束，已停止');assert.equal(texts['/main/player/timer/label'],'定时');
action('stations');action('cat1');action('row1');assert.equal(state.station,'naps-0');
ctx.brookesia_app.on_stop();assert.equal(state.active,false);start();assert.equal(texts['/main/player/title'],'Fun Kids Naps','Selection persists');
for(let i=0;i<stations.length;i++){action('stations');action('cat'+['儿童','音乐','资讯'].indexOf(stations[i].group));const local=stations.filter(s=>s.group===stations[i].group).findIndex(s=>s.id===stations[i].id);action('row'+local);if(!JSON.parse(saved['/littlefs/radio-settings.json']).favorites.includes(stations[i].id))action('favorite');}
action('stations');action('cat3');action('listNext');assert.equal(bindings['/main/stations/row2:hidden'],'false');action('listNext');assert.equal(bindings['/main/stations/row2:hidden'],'true');assert.equal(texts['/main/stations/footer/label'],'下一页 3/3');
state={...state,state:'Error',error:'network error',active:false};ctx.brookesia_app.on_timer();assert.equal(texts['/main/player/status'],'播放失败，请切换频道或重试');
console.log('Radio lifecycle, silent start, playback controls, all categories, favorites pagination, persistence, timer and hardware-volume refresh passed.');
