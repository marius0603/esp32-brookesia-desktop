const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),code=fs.readFileSync(root+'/src/app/main.js','utf8');
const layout=JSON.parse(fs.readFileSync(root+'/src/res/screens/main.json','utf8')),resources=new Set(JSON.parse(fs.readFileSync(root+'/src/res/images/index.json','utf8')).images.map(i=>i.id));
const nodes=new Map();function walk(n,p=''){p+='/'+n.id;nodes.set(p,n);for(const c of n.children||[])walk(c,p);}walk(layout);
function setup({now=Date.UTC(2026,10,9,15,59,59),weatherCode=2,battery=86,online=true}={}){
 const env={now,battery,online,asleep:false,calls:[],files:{},timer:0};
 env.files['/littlefs/clock-face.json']={face:2};
 env.files['/littlefs/weather-cache.json']={mode:'shanghai',location:{city:'上海',latitude:31.2304,longitude:121.4737},received_at:now-1000,data:{current:{temperature_2m:23,weather_code:weatherCode,is_day:1},utc_offset_seconds:28800,daily:{time:['2026-11-09','2026-11-10'],sunrise:['2026-11-09T06:15','2026-11-10T06:16'],sunset:['2026-11-09T16:59','2026-11-10T16:58']}}};
 class Clock extends Date{static now(){return env.now;}}
 const context=vm.createContext({Date:Clock,brookesia:{subscribe_event(){},start_service:n=>n,call_function(h,n,j){
  const a=JSON.parse(j);env.calls.push({h,n,a});let data=null;
  if(n==='ExecuteBatch'){data={Success:true,Results:a.Commands.map((cmd,i)=>{env.calls.push({h,n:cmd.Name,a:cmd.Params});assert(!cmd.Params.Path||nodes.has(cmd.Params.Path));return {Name:cmd.Name,Data:{AnimationId:100+i}};})};}

  if(n==='FSReadText')data=JSON.stringify(env.files[a.Path]??null);
  if(n==='FSWriteText')env.files[a.Path]=JSON.parse(a.Data);
  if(n==='GetGeneralState')data=env.online?'Connected':'Disconnected';
  if(h==='DeviceModes'&&n==='GetState')data={battery_status:env.battery,screen_asleep:env.asleep};
  if(n==='StartPeriodic')data=++env.timer;
  if(n==='SetText'||n==='SetViewSrc'||n==='SetBinding'){
   assert(nodes.has(a.Path),a.Path);if(n==='SetViewSrc')assert(resources.has(a.Src),'unknown source '+a.Src);
   if(n==='SetBinding')assert(Object.values(nodes.get(a.Path).bindings||{}).includes(a.Key),'missing binding '+a.Path+' '+a.Key);
  }
  if(n==='SetBindings')for(const u of a.Updates){assert(nodes.has(u.Path));assert(Object.values(nodes.get(u.Path).bindings||{}).includes(u.Key));}
  return JSON.stringify({success:true,data});
 }}});
 vm.runInContext(code,context);env.app=context.brookesia_app;env.app.on_start();
 env.step=(ms,name='clock')=>{env.now+=ms;env.app.on_timer(1,name);};
 env.src=p=>env.calls.filter(c=>c.n==='SetViewSrc'&&c.a.Path===p).at(-1)?.a.Src;
 return env;
}
const e=setup();assert.equal(e.files['/littlefs/clock-state.json'].digits,'235959');
assert.equal(nodes.get('/main/companion/scene').placement.width,480);
assert.equal(nodes.get('/main/companion/scene').placement.height,216);assert.equal(nodes.get('/main/companion/motion').placement.width,216);
assert.equal(nodes.get('/main/status/network').placement.x+nodes.get('/main/status/network').placement.width/2,240);
assert.equal(nodes.get('/main/status/battery').type,'image');
assert.equal(nodes.get('/main/status/weather/symbol').type,'image');
assert(!nodes.has('/main/companion/time'));
for(let i=0;i<3;i++)assert(nodes.get('/main/pager/page'+i).placement.y>=465);
let cut=e.calls.length;e.step(1000);
assert.equal(e.calls.slice(cut).filter(c=>c.n==='StartViewAnimation').length,30,'five native tracks per changed digit');
assert(!e.calls.slice(cut).some(c=>c.n==='StartPeriodic'&&c.a.IntervalMs===40),'cat flip must not use a per-frame JS timer');
const pending=e.calls.length;e.step(80,'flip');assert.equal(e.calls.length,pending,'native tween needs no intermediate GUI calls');e.now-=80;
assert.equal(e.calls.slice(cut).filter(c=>c.n==='SetViewSrc'&&c.a.Path.startsWith('/main/companion/d')&&c.a.Path.endsWith('/flap')).length,6,'midnight changes six digits');
for(let i=0;i<9;i++)e.step(40,'flip');
assert.equal(e.files['/littlefs/clock-state.json'].digits,'000000');
for(let i=0;i<6;i++)assert.equal(e.src('/main/companion/d'+i+'/bottom'),'clock_bottom_0');
function overlayHidden(t,i,part){return t.calls.filter(c=>c.n==='SetBindings').flatMap(c=>c.a.Updates).filter(u=>u.Path==='/main/companion/d'+i+'/'+part&&u.Key==='hidden').at(-1)?.Value;}
for(let i=0;i<6;i++)for(const part of ['flap','incoming'])assert.equal(overlayHidden(e,i,part),'true','midnight overlay must be hidden');
for(const [minute,sec,expected] of [[29,9,'122910'],[29,59,'123000']]){
 const t=setup({now:Date.UTC(2026,10,9,4,minute,sec)});t.step(1000);t.step(400);
 for(let i=0;i<6;i++){
  assert.equal(t.src('/main/companion/d'+i+'/bottom'),'clock_bottom_'+expected[i]);
  for(const part of ['flap','incoming'])assert.equal(overlayHidden(t,i,part),'true','carry cannot leave a half-page overlay');
 }
}
const interrupted=setup();interrupted.step(1000);interrupted.step(80,'flip');interrupted.app.on_pause();
for(let i=0;i<6;i++)for(const part of ['flap','incoming'])assert.equal(overlayHidden(interrupted,i,part),'true','pause settles all carry overlays');
cut=e.calls.length;e.step(640);
assert.equal(e.calls.slice(cut).filter(c=>c.n==='SetViewSrc'&&c.a.Path.endsWith('/flap')).length,1,'next second changes one digit');
for(let i=0;i<9;i++)e.step(40,'flip');
for(let i=0;i<12;i++)e.step(180);
const writes=e.calls.filter(c=>c.n==='FSWriteText').length;
for(let i=0;i<24;i++){e.step(180);e.app.on_timer(2,'flip');}
assert.equal(e.calls.filter(c=>c.n==='FSWriteText').length,writes,'steady seconds/cat animation cannot write Flash');
e.asleep=true;e.step(6000);cut=e.calls.length;
for(let i=0;i<10;i++){e.step(180);e.app.on_timer(2,'flip');}
assert(!e.calls.slice(cut).some(c=>c.n==='SetViewSrc'&&c.a.Path.startsWith('/main/companion/')),'sleep stops all animation');
e.asleep=false;cut=e.calls.length;e.step(6000);
assert(!e.calls.slice(cut).some(c=>c.n==='StartPeriodic'&&c.a.Name==='flip'),'wake settles directly');
e.app.on_pause();cut=e.calls.length;e.step(2000);e.app.on_timer(2,'flip');assert.equal(e.calls.length,cut);
e.app.on_resume();cut=e.calls.length;e.step(120000);assert(!e.calls.slice(cut).some(c=>c.n==='StartPeriodic'&&c.a.Name==='flip'),'clock jump settles directly');
for(const [value,src] of [[0,'0'],[20,'2'],[86,'9'],[100,'10'],[256+100,'charge_10'],[102,'usb'],[101,'unknown'],[undefined,'unknown']]){
 const t=setup({battery:value});if(value===undefined){t.battery=undefined;t.step(6000);}
 assert.equal(t.src('/main/status/battery'),'icon_battery_'+src);
}
for(const [weatherCode,symbol] of [[0,'clear'],[1,'partly'],[2,'partly'],[3,'clouds'],[45,'fog'],[61,'rain'],[66,'rain'],[71,'snow'],[85,'snow'],[95,'thunder'],[99,'thunder'],[42,'unknown']]){
 for(const day of [true,false]){const t=setup({weatherCode,now:Date.UTC(2026,10,9,day?4:12,0,0)});
 assert.equal(t.src('/main/status/weather/symbol'),'icon_weather_'+symbol+(['clear','partly'].includes(symbol)?'_'+(day?'day':'night'):''));}
}
assert.equal(setup({online:false}).src('/main/status/network'),'icon_wifi_off');
console.log('Companion: six-digit midnight/seconds, exact icon resources/layout, day/night weather, battery states, pause/wake/time-jump and no continuous Flash writes passed');
