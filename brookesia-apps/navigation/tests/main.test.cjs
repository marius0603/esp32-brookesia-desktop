const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const base=path.join(__dirname,'../src'),screen=JSON.parse(fs.readFileSync(base+'/res/screens/main.json','utf8'));
const allowed=new Set(['SystemGui','SystemCore','SystemTimer',...JSON.parse(fs.readFileSync(base+'/manifest.json','utf8')).services.map(s=>s.name)]);
const views=new Set(),texts={},bindings={},calls=[];function index(n,p=''){p+='/'+n.id;views.add(p);for(const c of n.children||[])index(c,p);}index(screen);
let lastVolume=null;let sample={},theme='dark',now=100000,modes={do_not_disturb:false,resume_volume:70};
class Clock extends Date{static now(){return now;}}
const ctx=vm.createContext({Date:Clock,console:{log(){}},brookesia:{start_service:n=>{assert.ok(allowed.has(n),'Undeclared service '+n);return n;},call_function(h,n,raw){
 const p=JSON.parse(raw);calls.push(n);if(h==='SystemGui'&&p.Path)assert.ok(views.has(p.Path));
 if(n==='SetVolume')lastVolume=p.Volume;
 if(n==='SetText')texts[p.Path]=p.Text;
 if(n==='SetBinding')bindings[p.Path+':'+p.Key]=p.Value;
 return JSON.stringify({success:true,data:n==='GetNavigationState'?sample:n==='GetEnvironment'?{theme_id:theme}:n==='GetState'?modes:n==='StartPeriodic'?99:null});
}}});
vm.runInContext('Array.from=undefined;',ctx); // Device JS subset must not require Array.from for notification text.
vm.runInContext(fs.readFileSync(base+'/app/main.js','utf8'),ctx);const app=ctx.brookesia_app;app.on_start();
assert.equal(texts['/main/volume'],'70%');assert.equal(texts['/main/status'],'等待手机连接');assert.equal(bindings['/main/arrow:hidden'],'true');
sample={received:true,stale:false,phase:0,source:0,turn:1,distance:200,remaining:1500,seconds:900,road:'示例道路'};app.on_timer();
assert.equal(texts['/main/distance'],'200 米');assert.equal(texts['/main/turn'],'向左转');assert.equal(texts['/main/details'],'剩余 1.5 公里  ·  15 分钟');
let prompts=()=>calls.filter(n=>n==='PlayNavigationPrompt').length;assert.equal(prompts(),1);app.on_timer();assert.equal(prompts(),1);
now+=9000;sample.distance=100;app.on_timer();assert.equal(prompts(),2);now+=9000;sample.distance=150;app.on_timer();assert.equal(prompts(),2);sample.distance=30;app.on_timer();assert.equal(prompts(),3);
sample.stale=true;app.on_timer();assert.equal(texts['/main/status'],'数据已过期');assert.equal(texts['/main/distance'],'--');assert.equal(bindings['/main/arrow:hidden'],'true');
sample.stale=false;sample.turn=99;sample.source=1;app.on_timer();assert.equal(texts['/main/turn'],'按手机提示');assert.equal(texts['/main/source'],'高德模拟');
sample.source=2;sample.turn=7;sample.distance=-1;sample.remaining=-1;sample.seconds=-1;app.on_timer();assert.equal(texts['/main/distance'],'--');assert.equal(texts['/main/details'],'剩余 --  ·  -- 分钟');assert.equal(texts['/main/source'],'高德通知');
now+=9000;sample.turn=1;sample.distance=50;sample.road='前方50米左转';app.on_timer();assert.equal(prompts(),4);
now+=9000;sample.distance=49;sample.road='前方49米左转';app.on_timer();assert.equal(prompts(),4,'Changing notification distance must not replay the same stage');
now+=500;sample.turn=2;sample.road='前方49米右转';app.on_timer();assert.equal(prompts(),5,'A changed direction cancels old speech promptly');
app.on_action('voice');now+=9000;sample.turn=1;app.on_timer();assert.equal(prompts(),5);
app.on_action('voice');modes.do_not_disturb=true;app.on_timer();assert.equal(prompts(),5);modes.do_not_disturb=false;modes.resume_volume=0;app.on_timer();assert.equal(prompts(),5);
sample.road='路'.repeat(15)+'😀再';app.on_timer();assert.equal(texts['/main/road'],'路'.repeat(15)+'…');
sample.phase=2;app.on_timer();assert.equal(texts['/main/status'],'导航已停止');assert.equal(bindings['/main/arrow:hidden'],'true');
app.on_pause();sample.phase=0;app.on_timer();assert.equal(texts['/main/status'],'导航已停止');
theme='light';app.on_resume();assert.equal(bindings['/main:background'],'#f5eddf');assert.equal(texts['/main/status'],'蓝牙同步中');modes.resume_volume=100;app.on_action('plus');assert.equal(lastVolume,100);modes.resume_volume=0;app.on_action('minus');assert.equal(lastVolume,0);app.on_stop();assert.ok(calls.includes('Stop'));
assert.ok(!calls.some(n=>/FSWrite|Http|Request/.test(n)),'No network, persistence or additional AMap calls');
console.log('Navigation UI: stale/stop/unknown maneuver/theme/pause checks passed');
