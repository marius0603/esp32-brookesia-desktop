// Exercise the real UI against strict document paths and a slow PIN service.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'../brookesia-apps/child-mode/src');
const nodes={};
function walk(node,parent=''){const p=parent+'/'+node.id;nodes[p]=node;for(const child of node.children||[])walk(child,p);}
walk(JSON.parse(fs.readFileSync(path.join(root,'res/screens/main.json'),'utf8')));
function fixture(configured){
 const text={},bindings={},pinCalls=[],writes=[];let now=0;
 const stations=[{id:'suzhou-qtfm',name:'苏州儿童广播'},{id:'junior-0',name:'Fun Kids Junior'},
  {id:'story-quest-0',name:'Story Quest'},{id:'cnr-classic',name:'经典音乐广播'},{id:'naps-0',name:'Fun Kids Naps'}];
 const state={configured,enabled:false,allow_audiobook:true,allow_songs:true,allow_radio:false,radio_allowed_stations:[],allow_weather:true,allow_clock:true,allow_assistant:false,
  max_volume:30,daily_minutes:30,remaining_seconds:1800,night_enabled:false,night_start:21,night_end:8,locked_seconds:0};
 const brookesia={start_service:name=>name,call_function:(service,name,json,timeout)=>{
  const p=JSON.parse(json);let data;
  if(service==='SystemGui'){
   if(name==='SetText'){assert.equal(nodes[p.Path]?.type,'label',p.Path);text[p.Path]=p.Text;}
   else if(name==='SetBindings')for(const u of p.Updates){assert.equal(nodes[u.Path]?.bindings['commonProps.hidden'],u.Key);bindings[u.Path]=u.Value;}
   else assert.equal(name,'SubscribeAction');
  }else if(service==='ChildMode'){
   if(name==='GetState')data={...state};
   else if(name==='GetRadioStations')data={stations};
   else if(['SetupPin','VerifyPin','ChangePin'].includes(name)){
    pinCalls.push({name,timeout});
    if(timeout<15000)throw Error('timeout 1000ms');
    if(p.Pin!=='135790')return JSON.stringify({success:false,error_message:'PIN 不正确'});
    state.configured=true;data={token:'test-session'};
   }else if(name==='Configure'){assert.equal(p.Token,'test-session');writes.push(p.Settings);Object.assign(state,p.Settings);}else assert.equal(name,'Lock');
  }else{assert.equal(service,'SystemTimer');data=1;}
  return JSON.stringify({success:true,data});
 }};
 const context={brookesia,console,Date:{now:()=>now}};
 vm.runInNewContext(fs.readFileSync(path.join(root,'app/main.js'),'utf8'),context);
 const app=context.brookesia_app;app.on_start();
 return {app,text,bindings,pinCalls,state,writes,jumpClock:()=>{now+=365*86400000;},enter:pin=>{for(const c of pin)app.on_action('digit'+c);app.on_action('enter');}};
}
const first=fixture(false);first.enter('135790');assert.equal(first.bindings['/main/gate'],'false');
first.enter('135790');assert.equal(first.bindings['/main/control'],'false');assert.equal(first.bindings['/main/gate'],'true');
assert.equal(first.pinCalls[0].name,'SetupPin');
const existing=fixture(true);existing.enter('111111');
for(let i=0;i<8;i++)existing.app.on_timer();
assert.equal(existing.text['/main/status'],'PIN 不正确');
existing.enter('135790');assert.equal(existing.bindings['/main/control'],'false');
existing.app.on_action('apps');assert.equal(existing.text['/main/apps/book/label'],'听书：允许');existing.app.on_action('back_apps');
existing.jumpClock();existing.app.on_timer();assert.equal(existing.bindings['/main/control'],'false');
existing.app.on_pause();assert.equal(existing.bindings['/main/gate'],'false');
assert.ok([...first.pinCalls,...existing.pinCalls].every(c=>c.timeout===15000));
console.log('PASS: first setup, slow PIN verification, persistent wrong-PIN message, clock jump, pause lock');

const limits=fixture(true);limits.enter('135790');for(let i=0;i<7;i++)limits.app.on_action('volume_plus');assert.equal(limits.text['/main/control/volume'],'音量上限 100%');limits.app.on_action('volume_plus');assert.equal(limits.text['/main/control/volume'],'音量上限 100%');for(let i=0;i<12;i++)limits.app.on_action('volume_minus');assert.equal(limits.text['/main/control/volume'],'音量上限 10%');
console.log('PASS: parent volume limit reaches 100 and remains within 10..100');

const access=fixture(true);
access.app.on_action('channels');access.app.on_action('channel0');
assert.equal(access.writes.length,0);
access.enter('135790');access.app.on_action('apps');
assert.equal(access.text['/main/apps/songs/label'],'儿歌：允许');
assert.equal(access.text['/main/apps/radio/label'],'电台：关闭');
access.app.on_action('book');access.app.on_action('songs');access.app.on_action('radio');
assert.deepEqual(JSON.parse(JSON.stringify(access.writes)),[{allow_audiobook:false},{allow_songs:false},{allow_radio:true}]);
access.app.on_action('channels');assert.equal(access.text['/main/channels/channel0/label'],'苏州儿童广播  未允许');
access.app.on_action('channel0');assert.equal(access.text['/main/channels/channel0/label'],'苏州儿童广播  已允许');
access.app.on_action('channel_next');assert.equal(access.text['/main/channels/channel0/label'],'Fun Kids Naps  未允许');
assert.equal(access.bindings['/main/channels/channel1'],'true');
access.app.on_action('channel0');
assert.deepEqual(access.state.radio_allowed_stations,['suzhou-qtfm','naps-0']);
access.app.on_action('channel_next');access.app.on_action('channel0');
assert.deepEqual(access.state.radio_allowed_stations,['naps-0']);
access.app.on_action('back_channels');assert.equal(access.text['/main/apps/channels/label'],'频道白名单 1');
access.app.on_pause();access.app.on_action('channel0');
assert.deepEqual(access.state.radio_allowed_stations,['naps-0']);
console.log('PASS: three separate switches, PIN-gated channel choices, pagination and revocation');
