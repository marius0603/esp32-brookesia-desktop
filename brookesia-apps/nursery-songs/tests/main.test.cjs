const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const src=path.join(__dirname,'../src');
const screen=JSON.parse(fs.readFileSync(path.join(src,'res/screens/main.json'))),views=new Map(),actions=new Set();
function visit(v,p=''){p+='/'+v.id;views.set(p,v);for(const e of v.events||[]){assert(!actions.has(e.action),'Document action must be unique: '+e.action);actions.add(e.action);}for(const c of v.children||[])visit(c,p);}
visit(screen);
let mounted=true,tracks=Array.from({length:20},(_,i)=>({path:'/sdcard/audiobooks/songs/'+i+'.mp3',title:'歌曲'+i}));
const lullabies=Array.from({length:10},(_,i)=>({path:'/sdcard/audiobooks/songs/lullabies/'+i+'.mp3',title:'摇篮曲'+i}));
tracks.push(...lullabies);
let state={path:'',state:'Idle',active:false},stored={},texts={},calls=[],now=20000;
class Clock extends Date{static now(){return now;}}
let desktopTheme=0;
const ctx=vm.createContext({Date:Clock,brookesia:{start_service:n=>n,call_function(h,n,s){
 const a=JSON.parse(s);calls.push({h,n,a});let data=null;if(n==='GetEnvironment')data={theme_id:desktopTheme===1?'dark':'light'};
 if(h==='SystemGui'&&a.Path){assert(views.has(a.Path),'Unknown view '+a.Path);if(n==='SetBinding')assert(Object.values(views.get(a.Path).bindings||{}).includes(a.Key),'Missing binding '+a.Key);}
 if(n==='ListSongs')data={mounted,tracks};
 if(n==='List')throw Error('Songs must never list stories');
 if(n==='StorageRead'){if(!stored.player)return JSON.stringify({success:false,error:'missing'});data=stored.player;}
 if(n==='StorageWrite')stored.player=a.Data;
 if(n==='SetText')texts[a.Path]=a.Text;
 if(n==='GetState')data=h==='DeviceModes'?{resume_volume:57,do_not_disturb:false,desktop_theme_index:desktopTheme}:state;
 if(n==='SetSongMode')state={...state,song_play_mode:a.Mode};
 if(n==='Play')state={...state,path:a.Path,position:a.Position,duration:60,state:'Playing',active:true};
 if(n==='Pause')state={...state,state:'Paused'};
 if(n==='Resume')state={...state,state:'Playing'};
 if(n==='Stop')state={...state,active:false,state:'Stopped'};
 if(n==='SetSleepTimer')state={...state,sleep_active:a.Minutes>0,sleep_minutes:a.Minutes,sleep_remaining_seconds:a.Minutes*60};
 if(n==='SetPlayMode')throw Error('Song modes must not overwrite story preferences');
 return JSON.stringify({success:true,data});
}}});
vm.runInContext(fs.readFileSync(path.join(src,'app/main.js'),'utf8'),ctx);
const app=ctx.brookesia_app;app.on_start();
assert(!calls.some(x=>x.n==='Play'),'Opening is silent');
assert.equal(texts['/main/collections/nursery/label'],'快乐儿歌 · 20首');
assert.equal(texts['/main/collections/lullaby/label'],'摇篮曲 · 10首');
app.on_action('nursery');
assert(!calls.some(x=>x.n==='Play'),'Choosing a collection is silent');
app.on_action('previous');assert.equal(state.path,tracks[19].path,'Nursery previous wraps inside its collection');
app.on_action('next');assert.equal(state.path,tracks[0].path);
app.on_action('toggle');assert.equal(state.state,'Paused');
state={...state,active:false,state:'Stopped'};

app.on_action('toggle');assert.equal(state.path,tracks[0].path);
app.on_action('toggle');assert.equal(state.state,'Paused');app.on_action('toggle');assert.equal(state.state,'Playing');
state={...state,position:60,state:'Ended',active:false};app.on_timer();assert.equal(state.path,tracks[1].path,'End advances once');
app.on_timer();assert.equal(state.path,tracks[1].path);
app.on_action('songs');app.on_action('listNext');app.on_action('row2');assert.equal(state.path,tracks[6].path,'Paged song row maps correctly');
app.on_action('sleep');app.on_action('choice2');app.on_action('timerConfirm');assert.equal(state.sleep_minutes,30);
app.on_action('mode');assert.equal(JSON.parse(stored.player).mode,'random');app.on_action('mode');assert.equal(JSON.parse(stored.player).mode,'repeat_one');
state={...state,position:60,state:'Ended',active:false};app.on_timer();assert.equal(state.path,tracks[6].path,'Single song loops');
state={...state,song_play_mode:'sequence'};app.on_timer();assert.equal(texts['/main/player/mode/label'],'顺序播放','Remote song mode refreshes the open device app');
state={...state,position:23,state:'Paused'};app.on_timer();app.on_stop();assert.equal(JSON.parse(stored.player).bookmark.position,23);
app.on_start();app.on_action('toggle');assert.equal(state.position,23,'Song bookmark survives restart');
app.on_action('collections');app.on_action('lullaby');
assert.equal(state.active,false,'Switching collection stops the previous song');
app.on_action('toggle');assert.equal(state.path,lullabies[0].path);
assert.match(texts['/main/player/count'],/摇篮曲.*10/);
app.on_action('previous');assert.equal(state.path,lullabies[9].path,'Previous never leaves lullabies');
app.on_action('next');assert.equal(state.path,lullabies[0].path,'Next wraps within lullabies');
app.on_action('songs');app.on_action('listNext');app.on_action('listNext');app.on_action('row1');assert.equal(state.path,lullabies[9].path);
state={...state,position:17,state:'Paused'};app.on_timer();app.on_stop();
app.on_start();app.on_action('lullaby');app.on_action('toggle');assert.equal(state.position,0,'Explicit collection entry starts cleanly');
app.on_action('collections');app.on_action('nursery');app.on_action('toggle');assert.equal(state.path,tracks[6].path);assert.equal(state.position,0,'Explicit nursery entry starts cleanly');
state={...state,path:lullabies[0].path,song_play_mode:'sequence',position:0,state:'Playing',active:true};app.on_timer();
state={...state,position:60,state:'Ended',active:false};app.on_timer();assert.equal(state.path,lullabies[1].path,'Lullaby EOF stays inside its collection');
app.on_action('collections');app.on_action('credits');app.on_action('creditsBack');
state={...state,path:tracks[0].path,position:60,state:'Stopped',active:false};app.on_action('nursery');app.on_action('toggle');assert.equal(state.active,true);assert.equal(state.position,0,'Stale end position cannot silence the first play');
state={path:'/sdcard/audiobooks/bedtime/story.mp3',state:'Playing',active:true};app.on_timer();calls=[];app.on_stop();assert(!calls.some(x=>x.n==='Stop'),'Never stops a different owner');
mounted=false;tracks=[];app.on_start();assert.match(texts['/main/player/status'],/SD/);app.on_action('toggle');
assert(!calls.some(x=>x.n==='Play'));
console.log('Nursery/lullaby collections, independent bookmarks, collection EOF and navigation passed. Nursery songs: isolated catalog, pagination, pause/resume, advance/loop, timer, SD bookmark, missing card passed');

desktopTheme=1;ctx.brookesia_app.on_timer();assert(calls.some(c=>c.n==='SetBinding'&&c.a.Path==='/main'&&c.a.Value==='#101723'),'Dark desktop theme must reach the app background');
desktopTheme=0;ctx.brookesia_app.on_timer();assert(calls.some(c=>c.n==='SetBinding'&&c.a.Path==='/main'&&c.a.Value==='#f4ebdd'),'Light desktop theme must reach the app background');
