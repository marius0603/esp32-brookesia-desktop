const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../src/app/main.js'),'utf8');
let bindings=[],calls=[],texts={},stored={},tracks=[],mounted=false,volume=20,volumeCap=100,quiet=false,offlineListening=false,selection=0,locked=false;
let state={path:'',state:'Idle',position:0,duration:0,active:false},now=20000;
const document=JSON.parse(fs.readFileSync(path.join(__dirname,'../src/res/screens/main.json'),'utf8')),views=new Set();
function indexViews(node,parent=''){const key=parent+'/'+node.id;views.add(key);for(const c of node.children||[])indexViews(c,key);}
indexViews(document);
class Clock extends Date{static now(){return now;}}
const ctx=vm.createContext({Date:Clock,brookesia:{start_service:n=>{bindings.push(n);return n;},call_function(h,n,s){
 const a=JSON.parse(s);calls.push({h,n,a});let data=null;
 if(h==='SystemGui'&&a.Path)assert(views.has(a.Path),'Missing GUI view: '+a.Path);
 if(n==='FSReadText'){if(!stored[a.Path])return JSON.stringify({success:false,error:'missing'});data=stored[a.Path];}
 if(n==='FSWriteText')stored[a.Path]=a.Data;
 if(n==='SetVolume')volume=Math.min(volumeCap,a.Volume);
 if(n==='GetVolume')data=volume;
 if(n==='List')data={mounted,tracks};
 if(n==='GetState')data=h==='DeviceModes'?{do_not_disturb:quiet,resume_volume:30}:h==='OfflineVoice'?{listening:offlineListening}:state;
 if(n==='ListenNow')offlineListening=true;
 if(n==='SetText')texts[a.Path]=a.Text;
 if(n==='SetBinding'&&a.Path==='/main/sleep/choice')selection=Number(a.Value);
 if(n==='GetBinding'&&a.Path==='/main/sleep/choice')data=String(selection);
 if(n==='LockScreen')locked=true;
 if(n==='Play')state={...state,path:a.Path,state:'Playing',position:a.Position,duration:60,active:true};
 if(n==='Pause')state={...state,state:'Paused'};
 if(n==='Resume')state={...state,state:'Playing'};
 if(n==='Stop')state={...state,state:'Stopped',active:false};
 if(n==='SetSleepTimer')state={...state,sleep_active:a.Minutes>0,sleep_minutes:a.Minutes,sleep_remaining_seconds:a.Minutes*60,sleep_fading:false,sleep_completed:false};
 return JSON.stringify({success:true,data});}}});
vm.runInContext(code,ctx);ctx.brookesia_app.on_start();
assert.equal(texts['/main/sleep/sleepStatus'],'');
assert.match(texts['/main/player/status'],/未检测到 SD 卡/);
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
assert.equal(calls.filter(c=>c.n==='SubscribeAction'&&['scan','test','quieter','louder','back','forward','sleep15','sleep30','sleep45','sleepOff'].includes(c.a.Action)).length,0);
for(const [selected,minutes] of [[1,15],[2,30],[3,45]]){
 selection=selected;ctx.brookesia_app.on_action('sleepChoice');
 assert.equal(calls.filter(c=>c.n==='SetSleepTimer').at(-1).a.Minutes,minutes);
 assert.match(texts['/main/sleep/sleepStatus'],new RegExp(minutes+':00'));
}
state={...state,sleep_active:true,sleep_fading:true,sleep_remaining_seconds:65};ctx.brookesia_app.on_timer();
assert.equal(texts['/main/sleep/sleepStatus'],'01:05');
const timerCalls=calls.filter(c=>c.n==='SetSleepTimer').length;ctx.brookesia_app.on_action('next');
assert.equal(state.sleep_active,true);assert.equal(calls.filter(c=>c.n==='SetSleepTimer').length,timerCalls);
selection=0;ctx.brookesia_app.on_action('sleepChoice');assert.equal(calls.filter(c=>c.n==='SetSleepTimer').at(-1).a.Minutes,0);
const beforeInvalid=calls.filter(c=>c.n==='SetSleepTimer').length;
for(const invalid of [-1,4,1.5,'bad','']){selection=invalid;ctx.brookesia_app.on_action('sleepChoice');}
assert.equal(calls.filter(c=>c.n==='SetSleepTimer').length,beforeInvalid);
state={...state,sleep_active:true,sleep_minutes:30};ctx.brookesia_app.on_timer();assert.equal(selection,2);
assert.equal(calls.filter(c=>c.n==='SetSleepTimer').length,beforeInvalid,'Polling must not restart the countdown');
state={...state,sleep_active:false};ctx.brookesia_app.on_timer();assert.equal(selection,0);
ctx.brookesia_app.on_action('back');ctx.brookesia_app.on_action('forward');assert.equal(calls.filter(c=>c.n==='Seek').length,0);
const plays=calls.filter(c=>c.n==='Play').length;
state={...state,state:'SleepEnded',active:false,position:42,sleep_completed:true};ctx.brookesia_app.on_timer();
assert.equal(calls.filter(c=>c.n==='Play').length,plays); // Never auto-advance after sleep.
assert.equal(JSON.parse(stored['/littlefs/audiobook-bookmark.json']).position,42);
assert.equal(texts['/main/sleep/sleepStatus'],'已结束');
volume=25;ctx.brookesia_app.on_timer();assert.equal(texts['/main/header/volume'],'音量 25%');
quiet=true;volume=0;ctx.brookesia_app.on_timer();assert.equal(texts['/main/header/volume'],'音量 30% · 静音');
quiet=false;volume=30;ctx.brookesia_app.on_timer();assert.equal(texts['/main/header/volume'],'音量 30%');
const screen=JSON.parse(fs.readFileSync(path.join(__dirname,'../src/res/screens/main.json'),'utf8'));
const ids=screen.children.map(n=>n.id);assert(!ids.includes('seek')&&!ids.includes('sound'));
assert.equal(ids[0],'header');assert(!ids.includes('lockHint'));
assert(screen.children.find(n=>n.id==='header').children.some(n=>n.id==='volume'));
assert.equal(screen.children.find(n=>n.id==='player').children.find(n=>n.id==='chapter').style.font,'${font.audiobook_title}');
const resources=JSON.parse(fs.readFileSync(path.join(__dirname,'../src/res/root.json'),'utf8'));
assert(!resources.assets.includes('fonts/index.json'),'Runtime app documents cannot register fontSet assets');
const systemFonts=JSON.parse(fs.readFileSync(path.join(__dirname,'../../../platform/super_s3_216/littlefs/system/fonts/index.json'),'utf8'));
assert.deepEqual(systemFonts.fonts.find(f=>f.id==='audiobook_title').fallbacks,['${font.zh_CN}']);
ctx.brookesia_app.on_action('offlineSpeak');assert.equal(calls.filter(c=>c.n==='ListenNow').length,1);ctx.brookesia_app.on_timer();assert.equal(texts['/main/tools/voice/label'],'正在听');
const tools=screen.children.find(n=>n.id==='tools');assert.equal(tools.children.find(n=>n.id==='voice').placement.height,48);
const choice=screen.children.find(n=>n.id==='sleep').children.find(n=>n.id==='choice');
assert.equal(choice.type,'dropdown');assert.deepEqual(choice.dropdownProps.options,['关闭','15分钟','30分钟','45分钟']);
assert.equal(choice.bindings['dropdownProps.selectedIndex'],'selected');
assert.deepEqual(fs.readFileSync(path.join(__dirname,'../src/res/images/launcher_icon.png')),fs.readFileSync(path.join(__dirname,'../../../themes/cartoon-q-v1/flash-fallback/audiobook.png')),'App updates must keep the Q theme icon');
assert(screen.children.reduce((sum,n)=>sum+n.placement.height,0)+(screen.children.length-1)*screen.layout.gap+2*screen.style.padding<=400);
const audioStops=calls.filter(c=>c.n==='Stop').length;
ctx.brookesia_app.on_action('lockScreen');assert(locked);
assert.equal(calls.filter(c=>c.n==='Stop').length,audioStops,'Screen lock must not stop the story');
assert.equal(calls.filter(c=>c.n==='SetSleepTimer').length,beforeInvalid,'Screen lock must preserve sleep countdown');
assert.equal(calls.filter(c=>c.n==='LockScreen').length,1);
for(const row of screen.children.filter(n=>['transport','tools'].includes(n.id)))for(const button of row.children){assert(button.placement.height>=48);if(button.children[0].type==='label')assert(button.children[0].style.fontSize>=22);}
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
assert.equal(texts['/main/player/chapter'],storyCases[0][1]);
for(let i=1;i<storyCases.length;i++){
 ctx.brookesia_app.on_action('next');
 assert.equal(texts['/main/player/chapter'],storyCases[i][1]);
 assert.equal(state.path,tracks[i].path,'Display names must not change playback paths');
}
// Resume/bookmarks and native next-track changes must use the same display names.
state={...state,path:tracks[2].path,state:'Paused',active:true,position:23};
ctx.brookesia_app.on_timer();assert.equal(texts['/main/player/chapter'],'小蝌蚪找妈妈');
ctx.brookesia_app.on_pause();ctx.brookesia_app.on_resume();
assert.equal(texts['/main/player/chapter'],'小蝌蚪找妈妈');
assert.equal(JSON.parse(stored['/littlefs/audiobook-bookmark.json']).path,tracks[2].path);
console.log('Story titles passed: all 10 Chinese names, filename fallback, chapter changes and bookmark resume');

// Real EOF transitions: sequence stops at the end, shuffle excludes the current
// chapter, and repeat-one restarts at zero without defeating sleep completion.
function setup(mode,count=2){
 tracks=Array.from({length:count},(_,i)=>({path:'/sdcard/audiobooks/'+i+'.wav'}));
 stored={'/littlefs/audiobook-play-mode.json':JSON.stringify({mode})};
 state={path:'',state:'Idle',position:0,duration:60,active:false};
 vm.runInContext(code,ctx);ctx.brookesia_app.on_start();ctx.brookesia_app.on_action('toggle');
}
function finish(){state={...state,state:'Ended',position:60,active:false};ctx.brookesia_app.on_timer();}
setup('sequence');finish();assert.equal(state.path,tracks[1].path);assert.equal(state.position,0);
let before=calls.filter(c=>c.n==='Play').length;finish();ctx.brookesia_app.on_timer();
assert.equal(calls.filter(c=>c.n==='Play').length,before,'Sequential last chapter must stop');
ctx.brookesia_app.on_stop();assert.equal(JSON.parse(stored['/littlefs/audiobook-bookmark.json']).position,0);
ctx.brookesia_app.on_start();ctx.brookesia_app.on_action('toggle');assert.equal(state.position,0);
setup('random');for(let i=0;i<12;i++){const previous=state.path;finish();assert.notEqual(state.path,previous);assert.equal(state.position,0);}
const previous=state.path;ctx.brookesia_app.on_action('next');assert.notEqual(state.path,previous);
setup('repeat_one');for(let i=0;i<3;i++){finish();assert.equal(state.path,tracks[0].path);assert.equal(state.position,0);}
ctx.brookesia_app.on_action('next');assert.equal(state.path,tracks[1].path,'Manual navigation remains available in repeat-one');
for(const mode of ['sequence','random','repeat_one']){
 setup(mode);before=calls.filter(c=>c.n==='Play').length;
 for(const status of ['Paused','Stopped','Error','SleepEnded']){state={...state,state:status,active:status==='Paused'};ctx.brookesia_app.on_timer();}
 assert.equal(calls.filter(c=>c.n==='Play').length,before,'Never restart after sleep, pause, stop or error');
 state={...state,path:'@tone',state:'Playing',active:true};ctx.brookesia_app.on_timer();finish();
 assert.equal(calls.filter(c=>c.n==='Play').length,before,'Test tone must not start stories');
}
setup('random',1);finish();assert.equal(state.path,tracks[0].path);
setup('repeat_one',0);finish();assert.equal(state.path,'');
setup('sequence');before=calls.filter(c=>c.n==='Play').length;
for(const mode of ['random','repeat_one','sequence']){
 ctx.brookesia_app.on_action('playMode');assert.equal(JSON.parse(stored['/littlefs/audiobook-play-mode.json']).mode,mode);
 assert.equal(calls.filter(c=>c.n==='SetViewSrc').at(-1).a.Src,'mode_'+mode);
}
assert.equal(calls.filter(c=>c.n==='Play').length,before,'Mode changes must not interrupt playback');
setup('random');ctx.brookesia_app.on_stop();vm.runInContext(code,ctx);ctx.brookesia_app.on_start();
assert.equal(calls.filter(c=>c.n==='SetViewSrc').at(-1).a.Src,'mode_random','Saved mode must survive app restart');
setup('invalid');assert.equal(calls.filter(c=>c.n==='SetViewSrc').at(-1).a.Src,'mode_sequence');
const savedBookmark=stored['/littlefs/audiobook-bookmark.json'];
state={...state,path:'/sdcard/audiobooks/removed.wav',state:'SleepEnded',active:false};ctx.brookesia_app.on_timer();
assert.equal(stored['/littlefs/audiobook-bookmark.json'],savedBookmark,'Stale sleep completion for an absent track must not overwrite the bookmark');
setup('sequence');
stored['/littlefs/audiobook-play-mode.json']=JSON.stringify({mode:'repeat_one'});
ctx.brookesia_app.on_timer();
assert.equal(calls.filter(c=>c.n==='SetViewSrc').at(-1).a.Src,'mode_repeat_one','Phone changes update the open device page');
finish();assert.equal(state.path,tracks[0].path,'Phone-selected repeat mode applies at EOF without reopening');
console.log('Playback modes passed: EOF ordering, shuffle exclusion, repeat-one, empty/single libraries, bookmarks, sleep/stop safeguards and persistence.');
