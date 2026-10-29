const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.join(__dirname,'..');
const raw=fs.readFileSync(path.join(root,'src/app/main.js'),'utf8');
const source=raw.replace(/\n\}\)\(\);\s*$/,'\nglobalThis.__test={validate,scheduled,clock,pose,read:()=>({mode,frames,hidden,panel,override,configError})};\n})();');
const doc=JSON.parse(fs.readFileSync(path.join(root,'src/res/screens/main.json'),'utf8')),views=new Map(),actions=new Set();
(function visit(n,p=''){p+='/'+n.id;views.set(p,n);for(const e of n.events||[]){assert(!actions.has(e.action),'Duplicate action '+e.action);actions.add(e.action);}for(const c of n.children||[])visit(c,p);})(doc);
const images=JSON.parse(fs.readFileSync(path.join(root,'src/res/images/index.json'),'utf8')).images;
const ids=new Set(images.map(i=>i.id));
const config=JSON.parse(fs.readFileSync(path.join(root,'content/schedule.json'),'utf8'));
const at=s=>Date.parse('2026-10-29T'+s+':00+08:00');
let now=at('10:00'),writes=[],calls=[],texts={},timers=new Set(),next=0,active='local.virtualpet';
class Clock extends Date {static now(){return now;}}
function create(bad=false){
 const ctx=vm.createContext({Date:Clock,brookesia:{start_service:n=>n,call_function(h,n,j){
  const a=JSON.parse(j);calls.push({h,n,a});let data=null;
  if(h==='SystemGui'&&a.Path)assert(views.has(a.Path),'Unknown view '+a.Path);
  if(n==='SetBinding')assert(Object.values(views.get(a.Path).bindings||{}).includes(a.Key),'Unknown binding');
  if(n==='SetBindings')for(const u of a.Updates){assert(views.has(u.Path));assert(Object.values(views.get(u.Path).bindings||{}).includes(u.Key));}
  if(n==='SetViewSrc')assert(ids.has(a.Src),'Unknown image '+a.Src);
  if(n==='SetText')texts[a.Path]=a.Text;
  if(n==='SubscribeAction')assert(actions.has(a.Action),'Unreachable action');
  if(n==='FSReadText')data=bad?'{}':JSON.stringify(config);
  if(n==='GetActiveApp')data={manifest:{id:active}};
  if(n==='FSWriteText')writes.push(JSON.parse(a.Data));
  if(n==='StartPeriodic'){data=++next;timers.add(data);}
  if(n==='Stop')timers.delete(a.TimerId);
  if(n==='StartViewAnimation'){assert(['y','opacity'].includes(a.Animation.property));data=++next;}
  if(n==='ExecuteBatch')data={Success:true,Results:a.Commands.map(command=>{const reply=JSON.parse(this.call_function(h,command.Name,JSON.stringify(command.Params)));return {Name:command.Name,Success:reply.success,Data:command.Name==='StartViewAnimation'?{AnimationId:reply.data}:reply.data};})};
  if(n==='PreloadImages'||n==='ReleaseImages')for(const id of a.Ids)assert(ids.has(id));
  return JSON.stringify({success:true,data});
 }}});
 vm.runInContext(source,ctx);return ctx;
}
const c=create();c.brookesia_app.on_start();assert.equal(c.__test.read().mode,'idle');assert.equal(timers.size,1);
for(const [time,mode,label] of [['00:00','sleep','睡个好觉'],['06:59','sleep','睡个好觉'],['07:00','idle','陪你一起'],['07:29','idle','陪你一起'],['07:30','eat','吃早餐'],['07:59','eat','吃早餐'],['08:00','idle','陪你一起'],['12:00','eat','吃午餐'],['12:30','idle','陪你一起'],['18:30','eat','吃晚餐'],['19:00','idle','陪你一起'],['21:59','idle','陪你一起'],['22:00','sleep','睡个好觉'],['23:59','sleep','睡个好觉']]){
 const s=c.__test.scheduled(at(time));assert.equal(s.mode,mode,time);assert.equal(s.label,label,time);
}
assert.equal(c.__test.scheduled(0).label,'等待校时');
assert.equal(c.__test.scheduled(NaN).mode,'idle');
assert.equal(c.__test.clock(at('12:34')).time,'12:34');
for(const mode of ['idle','happy','eat','sleep'])for(let n=0;n<100;n++)assert(ids.has(c.__test.pose(mode,n*125)));
const writesBefore=writes.length;
for(let n=0;n<200;n++){now+=50;c.brookesia_app.on_timer();}
assert(c.__test.read().frames>=4,'Animation advances');assert.equal(writes.length,writesBefore,'No per-frame storage writes');
assert(calls.some(c=>c.n==='StartViewAnimation'&&c.a.Animation.property==='opacity'),'Native pose tween');
assert(calls.some(c=>c.n==='StartViewAnimation'&&c.a.Animation.property==='y'&&c.a.Animation.playback),'Native breathing loop');
c.brookesia_app.on_action('feed');assert.equal(c.__test.read().mode,'eat');
const eatCommands=calls.filter(c=>c.n==='ExecuteBatch').at(-1).a.Commands;
assert(!eatCommands.some(c=>c.Name==='StartViewAnimation'),'No overlapping eating poses');
assert(eatCommands.some(c=>c.Name==='SetBindings'&&c.Params.Updates.some(u=>u.Key==='opacity'&&u.Value==='0')),'Only one eating layer is visible');
now+=12000;c.brookesia_app.on_timer();assert.equal(c.__test.read().mode,'idle');
c.brookesia_app.on_action('pet');assert.equal(c.__test.read().mode,'happy');
now=at('22:01');c.brookesia_app.on_timer();assert.equal(c.__test.read().mode,'sleep','Night overrides daytime interaction');
c.brookesia_app.on_action('feed');assert.equal(c.__test.read().mode,'sleep');
now=at('14:00');c.brookesia_app.on_timer();c.brookesia_app.on_action('schedule');assert(c.__test.read().panel);
c.brookesia_app.on_action('sleepPreview');assert.equal(c.__test.read().mode,'sleep');assert(!c.__test.read().panel);
now+=12000;c.brookesia_app.on_timer();assert.equal(c.__test.read().mode,'idle','Preview expires');
c.brookesia_app.on_action('feed');now-=1000;c.brookesia_app.on_timer();assert.equal(c.__test.read().mode,'idle','Clock correction clears transient state');
active='local.flipclock';now+=1000;c.brookesia_app.on_timer();assert(writes.at(-1).paused,'Foreground loss suspends pet even without lifecycle callback');
const awayFrames=c.__test.read().frames;now+=2000;c.brookesia_app.on_timer();assert.equal(c.__test.read().frames,awayFrames);
active='local.virtualpet';now+=1000;c.brookesia_app.on_timer();assert(!writes.at(-1).paused);assert.equal(timers.size,1);
c.brookesia_app.on_pause();assert.equal(timers.size,0);const before=calls.length;c.brookesia_app.on_timer();assert.equal(calls.length,before);
now=at('07:35');c.brookesia_app.on_resume();assert.equal(c.__test.read().mode,'eat');assert.equal(timers.size,1);assert.equal(c.__test.read().override,null);
c.brookesia_app.on_stop();assert.equal(timers.size,0);
const malformed=JSON.parse(JSON.stringify(config));malformed.sleep.end=1440;assert.throws(()=>c.__test.validate(malformed));
malformed.sleep.end=420;malformed.meals[0].duration=100;assert.throws(()=>c.__test.validate(malformed));
const fallback=create(true);fallback.brookesia_app.on_start();assert(fallback.__test.read().configError);fallback.brookesia_app.on_stop();
console.log('Pet passed: real-time meals, overnight sleep, frame playback, preview expiry, clock corrections, pause/resume and invalid schedule fallback.');
