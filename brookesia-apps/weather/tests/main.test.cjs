const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname,'../src/app/main.js'),'utf8');
const nodes={};
// Binding fields supported by the target Brookesia GUI ABI for these effects.
const supportedFxFields=new Set(['commonProps.hidden','style.bgColor','style.bgGradientColor','style.opacity','placement.x','placement.y']);
(function walk(node,parent=''){const p=parent+'/'+node.id;nodes[p]=node;for(const c of node.children||[])walk(c,p);})(JSON.parse(fs.readFileSync(path.join(__dirname,'../src/res/screens/main.json'),'utf8')));
const fixture = {current:{time:'2026-10-18T20:00',temperature_2m:23.6,relative_humidity_2m:82,
  apparent_temperature:26.1,is_day:0,precipitation:0.1,weather_code:51,wind_speed_10m:3.06},
  hourly:{time:Array.from({length:25},(_,i)=>new Date(Date.UTC(2026,9,18,20+i)).toISOString().slice(0,16)),
    temperature_2m:Array(25).fill(24),weather_code:Array(25).fill(51),is_day:Array(25).fill(0)}};

function harness(online=true, files={}) {
  let now=1792324800000, nextId=1;
  const calls=[], texts={};
  const ctx=vm.createContext({console,Date:{now:()=>now},brookesia:{
    start_service:name=>name, subscribe_event:()=>1,
    call_function(handle,name,json) {
      const p=JSON.parse(json); calls.push({handle,name,p}); let data=null;
      if(name==='SetBindings')for(const u of p.Updates){
        const field=Object.entries(nodes[u.Path]?.bindings||{}).find(([field,key])=>key===u.Key)?.[0];
        assert.ok(field,'Missing GUI binding '+u.Path+' '+u.Key);assert.ok(supportedFxFields.has(field),'Unsupported target GUI field '+field);
      }
      if (name==='FSReadText') {if (!(p.Path in files)) return JSON.stringify({success:false,error:'missing'});data=JSON.stringify(files[p.Path]);}
      if (name==='FSWriteText') files[p.Path]=JSON.parse(p.Data);
      if (name==='GetGeneralState') data=online?'Connected':'Started';
      if (name==='RequestAsync') data=nextId++;
      if (name==='StartPeriodic') data=99;
      if (name==='SetText') texts[p.Path]=p.Text;
      return JSON.stringify({success:true,data});
    }
  }});
  vm.runInContext(code.replace(/\n\}\)\(\);\s*$/, '\nglobalThis.__test = expression => eval(expression);\n})();'),ctx);
  return {app:ctx.brookesia_app,calls,texts,files,
    value:s=>ctx.__test(s), advance:n=>{now+=n;}, online:b=>{online=b;},
    requests:()=>calls.filter(c=>c.name==='RequestAsync'),
    complete:(id,body=fixture,status=200)=>ctx.brookesia_app.on_event('Http','RequestCompleted',
      JSON.stringify({RequestId:id,Response:{status_code:status,error:'Ok',body:JSON.stringify(body)}}))};
}
let count=0;
function test(name,fn) {fn();count++;console.log('ok '+name);}
test('missing values and WMO codes',()=>{
  const h=harness();assert.equal(h.value('num(null)'), '--');assert.equal(h.value('num(0)'), '0');
  assert.equal(h.value('condition(0,0)'), '晴夜');assert.equal(h.value('condition(97,1)'), '强雷雨');
  assert.throws(()=>h.value('validateWeather({current:{temperature_2m:null}})'));
});
test('offline -> connected starts asynchronous Shanghai request and updates GUI/cache',()=>{
  const h=harness(false);h.app.on_start();assert.equal(h.requests().length,0);
  h.online(true);h.app.on_timer();assert.equal(h.requests().length,1);
  assert.match(h.requests()[0].p.Request.url,/latitude=31.2304/);
  assert.equal(h.requests()[0].p.Request.tls_verify,'Verify');h.complete(1);
  assert.equal(h.texts['/main/content/temperature'],'23.6°C');assert.equal(h.texts['/main/content/condition'],'小毛毛雨');
  assert.equal(h.files['/littlefs/weather-cache.json'].data.current.temperature_2m,23.6);
  assert.equal(h.calls.filter(c=>c.name==='Request').length,0);
});
test('ten minute refresh, failure retains data, backoff, unrelated completion ignored',()=>{
  const h=harness();h.app.on_start();h.complete(1);h.advance(601000);h.app.on_timer();
  assert.equal(h.requests().length,2);h.complete(2,{},503);
  assert.equal(h.texts['/main/content/temperature'],'23.6°C');assert.match(h.texts['/main/content/condition'],/缓存/);
  h.advance(5000);h.app.on_timer();assert.equal(h.requests().length,2);
  h.advance(60000);h.app.on_timer();assert.equal(h.requests().length,3);
  h.complete(999);assert.equal(h.value('pending.id'),3);
});
test('disconnect cancels pending operation, reconnect retries',()=>{
  const h=harness();h.app.on_start();h.online(false);h.app.on_timer();
  assert.equal(h.value('pending'),null);assert.equal(h.calls.filter(c=>c.name==='CancelRequest').length,1);
  h.online(true);h.app.on_timer();assert.equal(h.requests().length,2);
});
test('IP location is explicitly marked and failure falls back to Shanghai',()=>{
  const h=harness(true,{'/littlefs/weather-settings.json':{mode:'auto'}});h.app.on_start();
  assert.match(h.requests().at(-1).p.Request.url,/ipwho.is/);
  h.complete(1,{success:true,city:'Test City',latitude:40,longitude:100});
  assert.match(h.requests().at(-1).p.Request.url,/latitude=40/);h.complete(2);
  assert.equal(h.files['/littlefs/weather-state.json'].location.origin,'网络出口推测');
  h.advance(601000);h.app.on_timer();h.complete(3,{success:false});
  assert.match(h.requests().at(-1).p.Request.url,/latitude=31.2304/);h.complete(4);
  assert.equal(h.files['/littlefs/weather-state.json'].location.origin,'定位失败，默认城市');
});
test('cache is restored offline and stale data is marked',()=>{
  const h=harness();h.app.on_start();h.complete(1);
  const restarted=harness(false,h.files);restarted.advance(1900000);restarted.app.on_start();
  assert.equal(restarted.texts['/main/content/temperature'],'23.6°C');
  assert.match(restarted.texts['/main/content/condition'],/缓存/);
  assert.equal(restarted.requests().length,0);
});
test('24 hourly entries, accurate themes, bounded droplet updates and pause',()=>{
  const h=harness();h.app.on_start();h.complete(1);
  assert.equal(h.value('hours24(data).length'),24);assert.equal(h.value('fxScene'),'rain');
  assert.equal(h.texts['/main/content/hourly/h23/time'],'19:00');
  assert.equal(h.value('sceneFor(97,1)'),'storm');assert.equal(h.value('sceneFor(75,0)'),'snow');
  assert.equal(h.value('sceneFor(45,1)'),'fog');assert.equal(h.value('sceneFor(0,0)'),'clear_night');
  for(let i=0;i<8;i++){h.advance(125);h.app.on_timer(99,'weather_fx');}
  assert.equal(h.value('fxFrames'),8);
  h.app.on_pause();const countBefore=h.calls.length;h.app.on_timer(99,'weather_fx');h.app.on_timer();
  assert.equal(h.calls.length,countBefore); // Neither background drawing nor Wi-Fi polling.
  assert.equal(h.files['/littlefs/weather-state.json'].fx_active,false);
});

test('all actual weather scenes animate using declared, bounded GUI updates',()=>{
  for(const [code,day,scene] of [[2,1,'cloudy_day'],[3,0,'cloudy_night'],[0,1,'clear_day'],[0,0,'clear_night'],[45,1,'fog'],[75,1,'snow'],[95,1,'storm']]){
    const h=harness(),value=JSON.parse(JSON.stringify(fixture));value.current.weather_code=code;value.current.is_day=day;
    h.app.on_start();h.complete(1,value);assert.equal(h.value('fxScene'),scene);assert.ok(h.value('fxTimer'));
    const start=h.calls.length;
    for(let i=0;i<8;i++){h.advance(250);h.app.on_timer(99,'weather_fx');}
    const batches=h.calls.slice(start).filter(c=>c.name==='SetBindings');
    assert.ok(batches.length>0,scene);assert.ok(batches.every(c=>c.p.Updates.length<=21));
    assert.equal(h.files['/littlefs/weather-state.json'].fx_frames,8);
    h.app.on_pause();assert.equal(h.value('fxTimer'),0);assert.equal(h.value('tickTimer'),0);
    h.app.on_resume();assert.ok(h.value('fxTimer'));assert.ok(h.value('tickTimer'));
    h.app.on_stop();h.app.on_start();assert.ok(h.value('fxTimer'),'restart must restart '+scene);
    h.advance(100000000000);h.app.on_timer(99,'weather_fx');assert.ok(h.value('fxElapsed')<=1,'clock sync must not jump the animation');
  }
});
test('night effect has visible movement and stops drawing while screen sleeps',()=>{
  const h=harness(),value=JSON.parse(JSON.stringify(fixture));value.current.weather_code=0;value.current.is_day=0;
  h.app.on_start();h.complete(1,value);
  const ys=[],opacities=[];
  for(let i=0;i<48;i++){
    h.advance(250);h.app.on_timer(99,'weather_fx');
    ys.push(h.value("fxValues['moon/y']"));opacities.push(h.value("fxValues['stars/s0/opacity']"));
  }
  assert.ok(Math.max(...ys)-Math.min(...ys)>=18);
  assert.ok(Math.max(...opacities)-Math.min(...opacities)>=200);
  h.value('screenAsleep=true;applyScene()');assert.equal(h.value('fxTimer'),0);
  const before=h.calls.length;h.app.on_timer(99,'weather_fx');assert.equal(h.calls.length,before);
  h.value('screenAsleep=false;applyScene()');assert.ok(h.value('fxTimer'));
});

test('static backgrounds use supported opacity and the full-screen shade cannot cover effects',()=>{
  for(const [path,node] of Object.entries(nodes))assert.ok(!('bgOpacity' in (node.style||{})),path+' uses unsupported background opacity');
  const backdrop=nodes['/main/backdrop'],shade=nodes['/main/backdrop/shade'];
  assert.ok(shade.style.opacity>0 && shade.style.opacity<=64,'shade must leave weather effects visible');
  assert.ok(!backdrop.style.opacity,'the effects parent must retain full opacity');
  assert.ok(!nodes['/main/content'].style.bgColor,'text container must not paint over the effects');
  assert.ok(backdrop.children.indexOf(shade)>backdrop.children.indexOf(nodes['/main/backdrop/stars']));
});

test('moon uses the existing transparent crescent asset and stars have no rectangular trail',()=>{
  const moon=nodes['/main/backdrop/moon'];assert.equal(moon.type,'image');assert.equal(moon.imageProps.src,'${image.wx_moon}');assert.ok(!moon.children && !moon.style.bgColor);
  const shooting=nodes['/main/backdrop/stars/shooting'];assert.equal(shooting.placement.width,10);assert.equal(shooting.placement.height,10);assert.equal(shooting.children.length,3);
  assert.ok(shooting.children.some(c=>c.id==='vertical'));assert.ok(shooting.children.some(c=>c.id==='horizontal'));assert.ok(!shooting.style.bgColor);
});

test('cloud layers use filled transparent cloud artwork rather than oval containers',()=>{
  for(const id of ['c0','c1']){
    const n=nodes['/main/backdrop/clouds/'+id];assert.equal(n.type,'image');
    assert.equal(n.imageProps.src,'${image.wx_cloud}');assert.ok(!n.style.bgColor && !n.children);
    assert.ok(n.style.opacity>=160);assert.equal(n.bindings['placement.x'],'x');assert.equal(n.bindings['placement.y'],'y');
  }
});
test('re-evaluating app in retained JavaScript context does not redeclare globals',()=>{const c=vm.createContext({});vm.runInContext(code,c);vm.runInContext(code,c);assert.equal(typeof c.brookesia_app.on_start,'function');});
console.log(count+' weather tests passed');
