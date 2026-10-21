// Exercise the real UI against strict document paths and a slow PIN service.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'../brookesia-apps/child-mode/src');
const nodes={};
function walk(node,parent=''){const p=parent+'/'+node.id;nodes[p]=node;for(const child of node.children||[])walk(child,p);}
walk(JSON.parse(fs.readFileSync(path.join(root,'res/screens/main.json'),'utf8')));
function fixture(configured){
 const text={},bindings={},pinCalls=[];let now=0;
 const state={configured,enabled:false,allow_audiobook:true,allow_weather:true,allow_clock:true,allow_assistant:false,
  max_volume:30,daily_minutes:30,remaining_seconds:1800,night_enabled:false,night_start:21,night_end:8,locked_seconds:0};
 const brookesia={start_service:name=>name,call_function:(service,name,json,timeout)=>{
  const p=JSON.parse(json);let data;
  if(service==='SystemGui'){
   if(name==='SetText'){assert.equal(nodes[p.Path]?.type,'label',p.Path);text[p.Path]=p.Text;}
   else if(name==='SetBindings')for(const u of p.Updates){assert.equal(nodes[u.Path]?.bindings['commonProps.hidden'],u.Key);bindings[u.Path]=u.Value;}
   else assert.equal(name,'SubscribeAction');
  }else if(service==='ChildMode'){
   if(name==='GetState')data={...state};
   else if(['SetupPin','VerifyPin','ChangePin'].includes(name)){
    pinCalls.push({name,timeout});
    if(timeout<15000)throw Error('timeout 1000ms');
    if(p.Pin!=='135790')return JSON.stringify({success:false,error_message:'PIN 不正确'});
    state.configured=true;data={token:'test-session'};
   }else assert.equal(name,'Lock');
  }else{assert.equal(service,'SystemTimer');data=1;}
  return JSON.stringify({success:true,data});
 }};
 const context={brookesia,console,Date:{now:()=>now}};
 vm.runInNewContext(fs.readFileSync(path.join(root,'app/main.js'),'utf8'),context);
 const app=context.brookesia_app;app.on_start();
 return {app,text,bindings,pinCalls,jumpClock:()=>{now+=365*86400000;},enter:pin=>{for(const c of pin)app.on_action('digit'+c);app.on_action('enter');}};
}
const first=fixture(false);first.enter('135790');assert.equal(first.bindings['/main/gate'],'false');
first.enter('135790');assert.equal(first.bindings['/main/control'],'false');assert.equal(first.bindings['/main/gate'],'true');
assert.equal(first.pinCalls[0].name,'SetupPin');
const existing=fixture(true);existing.enter('111111');
for(let i=0;i<8;i++)existing.app.on_timer();
assert.equal(existing.text['/main/status'],'PIN 不正确');
existing.enter('135790');assert.equal(existing.bindings['/main/control'],'false');
existing.jumpClock();existing.app.on_timer();assert.equal(existing.bindings['/main/control'],'false');
existing.app.on_pause();assert.equal(existing.bindings['/main/gate'],'false');
assert.ok([...first.pinCalls,...existing.pinCalls].every(c=>c.timeout===15000));
console.log('PASS: first setup, slow PIN verification, persistent wrong-PIN message, clock jump, pause lock');
