const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../src/app/main.js'),'utf8');
const source=code.replace(/\n\}\)\(\);\s*$/,'\nglobalThis.__test = expression => eval(expression);\n})();');
const screen=JSON.parse(fs.readFileSync(path.join(__dirname,'../src/res/screens/main.json'),'utf8'));
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'../src/manifest.json'),'utf8'));
assert.equal(manifest.package.name.zh_CN,'额度显示');
for(const card of screen.children.slice(1))assert.equal(card.children[0].style.fontSize,34);
assert.deepEqual(fs.readFileSync(path.join(__dirname,'../src/res/images/launcher_icon.png')),fs.readFileSync(path.join(__dirname,'../../../themes/cartoon-q-v1/flash-fallback/quota.png')));
const views=new Set();
function indexViews(node,parent=''){const p=parent+'/'+node.id;views.add(p);for(const child of node.children||[])indexViews(child,p);}
indexViews(screen);
let now=1000000;const calls=[],texts={},files={};
const packet={type:'quota',v:1,sampled_at:1000,bridge_at:1000,status:'ok',stale_after:180,
  windows:[{kind:'primary',used:27,reset_at:2000},{kind:'secondary',used:36,reset_at:4000}]};
class Clock extends Date{static now(){return now;}}
const ctx=vm.createContext({Date:Clock,console:{log(){}},brookesia:{start_service:x=>x,
  call_function(handle,name,json){const p=JSON.parse(json);calls.push({name,p});let data=null;
    if(p.Path && handle==='SystemGui')assert.ok(views.has(p.Path),'Missing view: '+p.Path);
    if(name==='SetBindings')for(const update of p.Updates)assert.ok(views.has(update.Path),'Missing binding view: '+update.Path);
    if(name==='FSReadText')data=JSON.stringify(packet);
    if(name==='FSWriteText')files[p.Path]=JSON.parse(p.Data);
    if(name==='StartPeriodic')data=99;
    if(name==='SetText')texts[p.Path]=p.Text;
    return JSON.stringify({success:true,data});}}});
vm.runInContext(source,ctx);ctx.brookesia_app.on_start();
assert.equal(texts['/main/card_primary/primary'],'73%');
assert.equal(texts['/main/card_secondary/secondary'],'64%');
assert.equal(texts['/main/sync/status'],'已同步');
assert.equal(ctx.__test('reset(1000+2*3600+13*60+45,1000)'),'02:13:45');
assert.equal(ctx.__test('reset(1000+3*86400+4*3600+20*60+11,1000)'),'3天 04:20:11');
assert.equal(ctx.__test('reset(null,1000)'),'暂无重置时间');
assert.equal(ctx.__test('reset(999,1000)'),'等待同步');
assert.equal(ctx.__test('pacX(100)'),358);
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
assert.equal(texts['/main/sync/status'],'已过期');
ctx.brookesia_app.on_timer(99,'pacman');assert.equal(ctx.__test('frames'),before);
packet.bridge_at=Math.floor(now/1000);packet.sampled_at=packet.bridge_at;packet.status='auth_required';
ctx.brookesia_app.on_timer(98,'quota');assert.equal(texts['/main/sync/status'],'需登录');
assert.equal(texts['/main/card_primary/primary'],'73%'); // Retain the last real allowance.
packet.status='ok';ctx.brookesia_app.on_timer(98,'quota');
assert.equal(texts['/main/sync/status'],'已同步');
ctx.brookesia_app.on_pause();assert.equal(ctx.__test('fxTimer'),0);
vm.runInContext(source,ctx);ctx.brookesia_app.on_start(); // Same retained VM: no global redeclaration.
assert.equal(typeof ctx.brookesia_app.on_timer,'function');
const original=ctx.brookesia.call_function;ctx.brookesia.call_function=(h,n,a)=>n==='Stop'?JSON.stringify({success:false,error:'timer already removed'}):original(h,n,a);assert.equal(ctx.brookesia_app.on_stop(),true);assert.equal(ctx.__test('fxTimer'),0);
console.log('Quota regression passed: exact percentages, partial beans, bounded animation, stale/pause and repeated load');
