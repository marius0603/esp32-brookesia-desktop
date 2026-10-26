const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../src/app/main.js'),'utf8');
let bindings=[],calls=[],texts={},stored={},tracks=[],mounted=false,volume=20,volumeCap=100,quiet=false,offlineListening=false;
let state={path:'',state:'Idle',position:0,duration:0,active:false},now=20000;
class Clock extends Date{static now(){return now;}}
const ctx=vm.createContext({Date:Clock,brookesia:{start_service:n=>{bindings.push(n);return n;},call_function(h,n,s){
 const a=JSON.parse(s);calls.push({h,n,a});let data=null;
 if(n==='FSReadText'){if(!stored[a.Path])return JSON.stringify({success:false,error:'missing'});data=stored[a.Path];}
 if(n==='FSWriteText')stored[a.Path]=a.Data;
 if(n==='SetVolume')volume=Math.min(volumeCap,a.Volume);
 if(n==='GetVolume')data=volume;
 if(n==='List')data={mounted,tracks};
 if(n==='GetState')data=h==='DeviceModes'?{do_not_disturb:quiet,resume_volume:30}:h==='OfflineVoice'?{listening:offlineListening}:state;
 if(n==='ListenNow')offlineListening=true;
 if(n==='SetText')texts[a.Path]=a.Text;
 if(n==='Play')state={...state,path:a.Path,state:'Playing',position:a.Position,duration:60,active:true};
 if(n==='Pause')state={...state,state:'Paused'};
 if(n==='Resume')state={...state,state:'Playing'};
 if(n==='Stop')state={...state,state:'Stopped',active:false};
 if(n==='SetSleepTimer')state={...state,sleep_active:a.Minutes>0,sleep_minutes:a.Minutes,sleep_remaining_seconds:a.Minutes*60,sleep_fading:false,sleep_completed:false};
 return JSON.stringify({success:true,data});}}});
vm.runInContext(code,ctx);ctx.brookesia_app.on_start();
assert.match(texts['/main/status'],/未检测到 SD 卡/);
ctx.brookesia_app.on_action('toggle');assert.equal(calls.filter(c=>c.n==='Play').length,0);
mounted=true;tracks=[{path:'/sdcard/audiobooks/test/001.mp3',title:'001.mp3'},{path:'/sdcard/audiobooks/test/002.wav',title:'002.wav'}];
ctx.brookesia_app.on_resume();ctx.brookesia_app.on_action('toggle');assert.equal(state.path,tracks[0].path);
state.position=33;ctx.brookesia_app.on_timer();ctx.brookesia_app.on_action('toggle');assert.equal(state.state,'Paused');
assert.equal(JSON.parse(stored['/littlefs/audiobook-bookmark.json']).position,33);
ctx.brookesia_app.on_action('toggle');assert.equal(state.state,'Playing');
ctx.brookesia_app.on_pause();const count=calls.filter(c=>c.n==='GetState').length;ctx.brookesia_app.on_timer();assert.equal(calls.filter(c=>c.n==='GetState').length,count);
ctx.brookesia_app.on_resume();ctx.brookesia_app.on_action('next');assert.equal(state.path,tracks[1].path);assert.equal(state.position,0);
ctx.brookesia_app.on_stop();assert.equal(state.active,false);
vm.runInContext(code,ctx);ctx.brookesia_app.on_start();ctx.brookesia_app.on_action('toggle');assert.equal(state.path,tracks[1].path);
assert.equal(calls.filter(c=>c.n==='SubscribeAction'&&['scan','test','quieter','louder'].includes(c.a.Action)).length,0);
for(const minutes of [15,30,45]){
 ctx.brookesia_app.on_action('sleep'+minutes);
 assert.equal(calls.filter(c=>c.n==='SetSleepTimer').at(-1).a.Minutes,minutes);
 assert.match(texts['/main/sleepStatus'],new RegExp(minutes+':00'));
}
state={...state,sleep_active:true,sleep_fading:true,sleep_remaining_seconds:65};ctx.brookesia_app.on_timer();
assert.equal(texts['/main/sleepStatus'],'正在淡出 01:05');
const timerCalls=calls.filter(c=>c.n==='SetSleepTimer').length;ctx.brookesia_app.on_action('next');
assert.equal(state.sleep_active,true);assert.equal(calls.filter(c=>c.n==='SetSleepTimer').length,timerCalls);
ctx.brookesia_app.on_action('sleepOff');assert.equal(calls.filter(c=>c.n==='SetSleepTimer').at(-1).a.Minutes,0);
const plays=calls.filter(c=>c.n==='Play').length;
state={...state,state:'SleepEnded',active:false,position:42,sleep_completed:true};ctx.brookesia_app.on_timer();
assert.equal(calls.filter(c=>c.n==='Play').length,plays); // Never auto-advance after sleep.
assert.equal(JSON.parse(stored['/littlefs/audiobook-bookmark.json']).position,42);
assert.equal(texts['/main/sleepStatus'],'定时结束 · 已停止');
volume=25;ctx.brookesia_app.on_timer();assert.equal(texts['/main/volume'],'音量 25% · 两侧实体键调节');
quiet=true;volume=0;ctx.brookesia_app.on_timer();assert.equal(texts['/main/volume'],'音量 30% · 勿扰静音');
quiet=false;volume=30;ctx.brookesia_app.on_timer();assert.equal(texts['/main/volume'],'音量 30% · 两侧实体键调节');
const screen=JSON.parse(fs.readFileSync(path.join(__dirname,'../src/res/screens/main.json'),'utf8'));
const ids=screen.children.map(n=>n.id);assert(!ids.includes('tools')&&!ids.includes('sound'));
assert.equal(screen.children.find(n=>n.id==='chapter').style.font,'${font.audiobook_title}');
const resources=JSON.parse(fs.readFileSync(path.join(__dirname,'../src/res/root.json'),'utf8'));
assert(!resources.assets.includes('fonts/index.json'),'Runtime app documents cannot register fontSet assets');
const systemFonts=JSON.parse(fs.readFileSync(path.join(__dirname,'../../../platform/super_s3_216/littlefs/system/fonts/index.json'),'utf8'));
assert.deepEqual(systemFonts.fonts.find(f=>f.id==='audiobook_title').fallbacks,['${font.zh_CN}']);
ctx.brookesia_app.on_action('offlineSpeak');assert.equal(calls.filter(c=>c.n==='ListenNow').length,1);ctx.brookesia_app.on_timer();assert.equal(texts['/main/voice/label'],'我在听，请说命令');
assert.equal(screen.children.find(n=>n.id==='voice').placement.height,54);
for(const row of screen.children.filter(n=>['transport','seek','sleep'].includes(n.id)))for(const button of row.children){assert(button.placement.height>=48);assert(button.children[0].style.fontSize>=22);}
console.log('Audiobook regression passed: automatic scan, playback/bookmarks, sleep presets/fade/completion, hardware-volume refresh and larger controls');

const bindingCount=bindings.length;
for(let i=0;i<120;i++){now+=1000;ctx.brookesia_app.on_timer();}
assert.equal(bindings.length,bindingCount,'Polling must reuse bindings instead of accumulating live service records');

// Exercise the visible chapter label with the SD service's actual path-shaped titles.
ctx.brookesia_app.on_stop();
const storyCases=[
 ['01-xiaoma-yueliang.mp3','小马和月亮灯'],['02-gudong.mp3','咕咚'],
 ['03-xiaokedou-zhao-mama.mp3','小蝌蚪找妈妈'],['04-wuya-heshui.mp3','乌鸦喝水'],
 ['05-xiaohouzi-xiashan.mp3','小猴子下山'],['06-hujiahuwei.mp3','狐假虎威'],
 ['07-zuojingguantian.mp3','坐井观天'],['08-xiaoma-guohe.mp3','小马过河'],
 ['09-xuehaizi.mp3','雪孩子'],['10-wangyangbulao.mp3','亡羊补牢'],
 ['另一篇故事.MP3','另一篇故事'],['new-story.wav','new-story']
];
tracks=storyCases.map(([file])=>({path:'/sdcard/audiobooks/bedtime/'+file,title:'/bedtime/'+file}));
stored={};vm.runInContext(code,ctx);ctx.brookesia_app.on_start();
assert.equal(texts['/main/chapter'],storyCases[0][1]);
for(let i=1;i<storyCases.length;i++){
 ctx.brookesia_app.on_action('next');
 assert.equal(texts['/main/chapter'],storyCases[i][1]);
 assert.equal(state.path,tracks[i].path,'Display names must not change playback paths');
}
// Resume/bookmarks and native next-track changes must use the same display names.
state={...state,path:tracks[2].path,state:'Paused',active:true,position:23};
ctx.brookesia_app.on_timer();assert.equal(texts['/main/chapter'],'小蝌蚪找妈妈');
ctx.brookesia_app.on_pause();ctx.brookesia_app.on_resume();
assert.equal(texts['/main/chapter'],'小蝌蚪找妈妈');
assert.equal(JSON.parse(stored['/littlefs/audiobook-bookmark.json']).path,tracks[2].path);
console.log('Story titles passed: all 10 Chinese names, filename fallback, chapter changes and bookmark resume');
