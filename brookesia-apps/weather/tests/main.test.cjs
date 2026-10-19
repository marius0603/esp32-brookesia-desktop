const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname,'../src/app/main.js'),'utf8');
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
  const countBefore=h.calls.length;h.app.on_pause();h.app.on_timer(99,'weather_fx');
  assert.equal(h.calls.length,countBefore+1); // One timer stop, no background drawing.
});
test('re-evaluating app in retained JavaScript context does not redeclare globals',()=>{const c=vm.createContext({});vm.runInContext(code,c);vm.runInContext(code,c);assert.equal(typeof c.brookesia_app.on_start,'function');});
console.log(count+' weather tests passed');
