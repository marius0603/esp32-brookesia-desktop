const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../src/app/main.js'),'utf8');
let now=Date.UTC(2026,9,18,15,59,59),calls=[],files={},stopped=false;
class Clock extends Date{static now(){return now;}}
const context=vm.createContext({Date:Clock,brookesia:{start_service:n=>n,call_function(h,n,s){
 const a=JSON.parse(s);calls.push({n,a});let data=null;
 if(n==='StartPeriodic')data=123;
 if(n==='FSWriteText')files[a.Path]=JSON.parse(a.Data);
 if(n==='Stop'&&stopped)return JSON.stringify({success:false,error:'timer already removed'});
 return JSON.stringify({success:true,data});}}});
vm.runInContext(code,context);context.brookesia_app.on_start();
assert.equal(files['/littlefs/clock-state.json'].digits,'2359');
now+=1000;context.brookesia_app.on_timer(1,'clock');
const changed=calls.filter(c=>c.n==='SetViewSrc'&&c.a.Path.endsWith('/flap'));
assert.equal(changed.length,4); // Midnight turns all four digits.
assert.ok(changed.every(c=>c.a.Src.includes('_top_')));
for(let i=0;i<9;i++){now+=40;context.brookesia_app.on_timer(2,'flip');}
assert.equal(files['/littlefs/clock-state.json'].digits,'0000');
assert.equal(files['/littlefs/clock-state.json'].frames,9);
assert.ok(calls.some(c=>c.n==='SetViewSrc'&&c.a.Src==='big_bottom_0'));
let start=calls.length;now=Date.UTC(2026,9,18,16,1,0);context.brookesia_app.on_timer(1,'clock');
assert.equal(calls.slice(start).filter(c=>c.n==='SetViewSrc'&&c.a.Path.endsWith('/flap')).length,1);
context.brookesia_app.on_pause();start=calls.length;now+=20000;context.brookesia_app.on_timer(1,'clock');context.brookesia_app.on_timer(2,'flip');assert.equal(calls.length,start);
context.brookesia_app.on_resume();assert.equal(files['/littlefs/clock-state.json'].digits,'0001');
start=calls.length;now+=120000;context.brookesia_app.on_timer(1,'clock');assert.equal(calls.slice(start).filter(c=>c.n==='StartPeriodic').length,0); // NTP jumps settle directly.
stopped=true;context.brookesia_app.on_stop();vm.runInContext(code,context);context.brookesia_app.on_start();
assert.equal(typeof context.brookesia_app.on_timer,'function');
console.log('Flip clock regression passed: UTC+8, midnight rollover, changed digits only, half-flap completion, background, resume, time jump and retained context');
