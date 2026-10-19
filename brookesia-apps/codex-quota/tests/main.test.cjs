const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../src/app/main.js'),'utf8');
const source=code.replace(/\n\}\)\(\);\s*$/,'\nglobalThis.__test = expression => eval(expression);\n})();');
let now=1000000;const calls=[],texts={},files={};
const packet={type:'quota',v:1,sampled_at:1000,bridge_at:1000,status:'ok',stale_after:180,
  windows:[{kind:'primary',used:27,reset_at:2000},{kind:'secondary',used:36,reset_at:4000}]};
class Clock extends Date{static now(){return now;}}
const ctx=vm.createContext({Date:Clock,console:{log(){}},brookesia:{start_service:x=>x,
  call_function(handle,name,json){const p=JSON.parse(json);calls.push({name,p});let data=null;
    if(name==='FSReadText')data=JSON.stringify(packet);
    if(name==='FSWriteText')files[p.Path]=JSON.parse(p.Data);
    if(name==='StartPeriodic')data=99;
    if(name==='SetText')texts[p.Path]=p.Text;
    return JSON.stringify({success:true,data});}}});
vm.runInContext(source,ctx);ctx.brookesia_app.on_start();
assert.equal(texts['/main/primary'],'短周期剩余 73%');
assert.equal(texts['/main/secondary'],'每周剩余 64%');
assert.equal(ctx.__test('pellets(27).reduce((a,b)=>a+b,0)/255*5'),73);
assert.equal(ctx.__test('usedValue({used:null})'),null);
assert.equal(ctx.__test('usedValue({used:200})'),100);
assert.equal(ctx.__test('usedValue({used:-2})'),0);
const beansBefore=ctx.__test('JSON.stringify(pellets(primaryUsed))');
for(let i=0;i<8;i++){now+=240;ctx.brookesia_app.on_timer(99,'pacman');}
assert.equal(files['/littlefs/quota-ui-state.json'].animation_frames,8);
assert.equal(files['/littlefs/quota-ui-state.json'].primary_remaining,73);
assert.equal(ctx.__test('JSON.stringify(pellets(primaryUsed))'),beansBefore);
now+=50000;ctx.brookesia_app.on_timer(98,'quota');const before=ctx.__test('frames');
ctx.brookesia_app.on_timer(99,'pacman');assert.equal(ctx.__test('frames'),before);
ctx.brookesia_app.on_pause();assert.equal(ctx.__test('fxTimer'),0);
vm.runInContext(source,ctx);ctx.brookesia_app.on_start(); // Same retained VM: no global redeclaration.
assert.equal(typeof ctx.brookesia_app.on_timer,'function');
const original=ctx.brookesia.call_function;ctx.brookesia.call_function=(h,n,a)=>n==='Stop'?JSON.stringify({success:false,error:'timer already removed'}):original(h,n,a);assert.equal(ctx.brookesia_app.on_stop(),true);assert.equal(ctx.__test('fxTimer'),0);
console.log('Quota regression passed: exact percentages, partial beans, bounded animation, stale/pause and repeated load');
