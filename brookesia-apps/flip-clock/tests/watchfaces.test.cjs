const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),code=fs.readFileSync(root+'/src/app/main.js','utf8'),layout=JSON.parse(fs.readFileSync(root+'/src/res/screens/main.json','utf8'));
const nodes=new Map();function walk(n,p=''){p+='/'+n.id;nodes.set(p,n);for(const c of n.children||[])walk(c,p);}walk(layout);
let now=Date.UTC(2026,10,9,4,30,0),calls=[],saved={},online=true,asleep=false,request=0;const conditions={temperature_2m:19,weather_code:2};
const solar={utc_offset_seconds:28800,daily:{time:['2026-11-09','2026-11-10'],sunrise:['2026-11-09T06:15','2026-11-10T06:16'],sunset:['2026-11-09T17:02','2026-11-10T17:01'],daylight_duration:[38820,38700]}};
saved['/littlefs/weather-cache.json']={mode:'shanghai',location:{city:'上海',latitude:31.2304,longitude:121.4737},received_at:now-3600000,data:{current:conditions,...solar}};
class Clock extends Date{static now(){return now;}}
const context=vm.createContext({Date:Clock,brookesia:{start_service:n=>n,subscribe_event(){},call_function(h,n,j){const a=JSON.parse(j);calls.push({h,n,a});let data=null;
 if(n==='ExecuteBatch'){data={Success:true,Results:a.Commands.map((cmd,i)=>{calls.push({h,n:cmd.Name,a:cmd.Params});return {Name:cmd.Name,Data:{AnimationId:100+i}};})};}

 if(n==='FSReadText'){if(!saved[a.Path])return JSON.stringify({success:false,error:'missing'});data=JSON.stringify(saved[a.Path]);}
 if(n==='FSWriteText')saved[a.Path]=JSON.parse(a.Data);
 if(n==='GetGeneralState')data=online?'Connected':'Disconnected';
 if(h==='DeviceModes'&&n==='GetState')data={battery_status:512|102,screen_asleep:asleep};
 if(n==='StartPeriodic')data=123;if(n==='RequestAsync')data=++request;
 if(n==='SetBinding'||n==='SetText'||n==='SetViewSrc'){assert(nodes.has(a.Path),'unknown path '+a.Path);if(n==='SetBinding')assert(Object.values(nodes.get(a.Path).bindings||{}).includes(a.Key),'missing binding '+a.Path+' '+a.Key);}
 if(n==='SetBindings')for(const u of a.Updates){assert(nodes.has(u.Path));assert(Object.values(nodes.get(u.Path).bindings||{}).includes(u.Key));}
 return JSON.stringify({success:true,data});}}});
vm.runInContext(code,context);context.brookesia_app.on_start();
const act=(n,x,y)=>context.brookesia_app.on_action(n,'/main/swipe',JSON.stringify({x,y}));
function swipe(dx,dy=0){now+=400;act('facePress',240,240);act('faceRelease',240+dx,240+dy);}
function text(p){return calls.filter(c=>c.n==='SetText'&&c.a.Path===p).at(-1)?.a.Text;}
function binding(p,key){return calls.filter(c=>c.n==='SetBinding'&&c.a.Path===p&&c.a.Key===key).at(-1)?.a.Value;}
swipe(-100);assert.equal(saved['/littlefs/clock-face.json'].face,1);assert(calls.some(c=>c.n==='SetViewSrc'&&c.a.Path==='/main/status/battery'&&c.a.Src==='icon_battery_usb'));assert(text('/main/status/weather/temperature').includes('19°C'));assert.equal(text('/main/status/weatherAge'),'天气缓存已过期');
const hands=calls.filter(c=>c.n==='SetBindings'&&c.a.Updates.some(u=>u.Path==='/main/analog/hour')).at(-1).a.Updates;assert.equal(hands.length,3);for(const h of hands){const points=JSON.parse(h.Value);assert.equal(points.length,2);for(const p of points)assert(p.x>=0&&p.x<=340&&p.y>=0&&p.y<=340);}
const id=request;context.brookesia_app.on_event('Http','RequestCompleted',JSON.stringify({RequestId:id+1,Response:{}}));assert.equal(text('/main/status/weatherAge'),'天气缓存已过期');
context.brookesia_app.on_event('Http','RequestCompleted',JSON.stringify({RequestId:id,Response:{status_code:200,error:'Ok',body:JSON.stringify({current:{temperature_2m:23.4,weather_code:0,is_day:1},...solar})}}));assert(text('/main/status/weather/temperature').includes('23°C'));assert(!saved['/littlefs/weather-cache.json'].data.current.temperature_2m.toString().includes('23'),'do not overwrite weather App cache');
swipe(-100);assert.equal(saved['/littlefs/clock-face.json'].face,2);assert.equal(saved['/littlefs/clock-state.json'].digits.slice(0,4),'1230');assert.equal(saved['/littlefs/clock-state.json'].digits.length,6);
function scene(){return calls.filter(c=>c.n==='SetViewSrc'&&c.a.Path==='/main/companion/motion').at(-1)?.a.Src;}
for(let i=0;i<12;i++){now+=180;context.brookesia_app.on_timer(1,'clock');}
assert(scene().startsWith('cat_day_'));
assert.equal(saved['/littlefs/clock-state.json'].solar.source,'sunrise_sunset');
assert.equal(binding('/main/status/weather','y'),'77');assert.equal(binding('/main/status/date','y'),'77');
assert(Number(binding('/main/status/weather/city','x'))>Number(binding('/main/status/date','x')));
const writeBefore=calls.filter(c=>c.n==='FSWriteText').length;for(let i=0;i<12;i++){now+=180;context.brookesia_app.on_timer(1,'clock');}
assert(calls.filter(c=>c.n==='SetViewSrc'&&c.a.Path==='/main/companion/motion').length>=20);assert.equal(calls.filter(c=>c.n==='FSWriteText').length,writeBefore,'steady animation must not write Flash');
asleep=true;now+=6000;context.brookesia_app.on_timer(1,'clock');const asleepCut=calls.length;
for(let i=0;i<10;i++){now+=180;context.brookesia_app.on_timer(1,'clock');}
assert(!calls.slice(asleepCut).some(c=>c.a.Path==='/main/companion/motion'),'sleep stops image changes');asleep=false;now+=6000;context.brookesia_app.on_timer(1,'clock');
// Exact solar boundaries, with stale is_day=1 deliberately contradicting night.
for(const [iso,expected] of [['2026-11-08T22:14:59Z','night'],['2026-11-08T22:15:00Z','day'],['2026-11-09T09:01:59Z','day'],['2026-11-09T09:02:00Z','night'],['2026-11-09T16:00:01Z','night'],['2026-11-09T22:16:00Z','day']]){
 now=Date.parse(iso);context.brookesia_app.on_timer(1,'clock');assert(scene().startsWith('cat_'+expected+'_'),iso+': '+scene());
}
swipe(0,100);assert.equal(saved['/littlefs/clock-face.json'].face,2,'vertical gesture must remain available');
context.brookesia_app.on_pause();const stopped=calls.length;now+=2000;context.brookesia_app.on_timer(1,'clock');assert.equal(calls.length,stopped);context.brookesia_app.on_resume();assert.equal(saved['/littlefs/clock-face.json'].face,2);
swipe(-100);assert.equal(saved['/littlefs/clock-face.json'].face,0);const cut=calls.length;now+=250;context.brookesia_app.on_timer(1,'clock');assert(!calls.slice(cut).some(c=>c.a.Path==='/main/companion/motion'));
swipe(100);assert.equal(saved['/littlefs/clock-face.json'].face,2);context.brookesia_app.on_stop();vm.runInContext(code,context);context.brookesia_app.on_start();assert.equal(binding('/main/companion','hidden'),'false','restore saved face');
// Short and mildly diagonal swipes should work without requiring a release.
const swipeLayer=nodes.get('/main/swipe');
assert.equal(swipeLayer.placement.y,0);assert.equal(swipeLayer.placement.height,456);
assert(swipeLayer.events.some(e=>e.type==='pressing'&&e.action==='faceMove'));
swipe(-34,20);assert.equal(saved['/littlefs/clock-face.json'].face,0);
swipe(34,-20);assert.equal(saved['/littlefs/clock-face.json'].face,2);
swipe(-40,34);assert.equal(saved['/littlefs/clock-face.json'].face,0);
swipe(31);assert.equal(saved['/littlefs/clock-face.json'].face,0,'small accidental movements must not switch');
now+=200;act('facePress',280,100);act('faceMove',312,110);
assert.equal(saved['/littlefs/clock-face.json'].face,2,'switch during motion');
act('faceMove',400,110);act('faceRelease',400,110);
assert.equal(saved['/littlefs/clock-face.json'].face,2,'one physical swipe switches exactly once');
now+=200;act('facePress',240,350);act('faceMove',245,300);act('faceRelease',340,280);
assert.equal(saved['/littlefs/clock-face.json'].face,2,'vertical intent is never reused for a horizontal switch');
now+=200;act('facePress',240,200);act('faceCancel',240,200);act('faceRelease',100,200);
assert.equal(saved['/littlefs/clock-face.json'].face,2,'cancel removes the old press');
context.brookesia_app.on_pause();act('facePress',240,200);act('faceMove',100,200);
assert.equal(saved['/littlefs/clock-face.json'].face,2,'paused clock ignores touch actions');
context.brookesia_app.on_resume();
// Cat decoding yields while a gesture is in progress, then resumes.
now+=200;act('facePress',240,300);const held=calls.length;
now+=180;context.brookesia_app.on_timer(1,'clock');
assert(!calls.slice(held).some(c=>c.n==='SetViewSrc'&&c.a.Path==='/main/companion/motion'));
context.brookesia_app.on_action('faceGesture','/main/swipe',JSON.stringify({direction:'left'}));
assert.equal(saved['/littlefs/clock-face.json'].face,0,'native flick fallback');
act('faceRelease',120,300);assert.equal(saved['/littlefs/clock-face.json'].face,0,'native and release do not double switch');
swipe(100);assert.equal(saved['/littlefs/clock-face.json'].face,2);
now+=200;act('facePress',240,300);now+=1600;const recovered=calls.length;context.brookesia_app.on_timer(1,'clock');
assert(calls.slice(recovered).some(c=>c.n==='SetViewSrc'&&c.a.Path==='/main/companion/motion'),'lost release cannot freeze the cat');
act('faceCancel',240,300);
console.log('Three clock faces: swipe/persistence, hands, sprite lifecycle, no per-frame writes, exact sunrise/sunset and next-day switch, weather cache and date/weather alignment passed');
