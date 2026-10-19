const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../src/app/main.js'),'utf8');
let calls=[],texts={},stored={},tracks=[],mounted=false;
let state={path:'',state:'Idle',position:0,duration:0,active:false},now=20000;
class Clock extends Date{static now(){return now;}}
const ctx=vm.createContext({Date:Clock,brookesia:{start_service:n=>n,call_function(h,n,s){
 const a=JSON.parse(s);calls.push({h,n,a});let data=null;
 if(n==='FSReadText'){if(!stored[a.Path])return JSON.stringify({success:false,error:'missing'});data=stored[a.Path];}
 if(n==='FSWriteText')stored[a.Path]=a.Data;
 if(n==='GetVolume')data=20;
 if(n==='List')data={mounted,tracks};
 if(n==='GetState')data=state;
 if(n==='SetText')texts[a.Path]=a.Text;
 if(n==='Play')state={path:a.Path,state:'Playing',position:a.Position,duration:60,active:true};
 if(n==='Pause')state={...state,state:'Paused'};
 if(n==='Resume')state={...state,state:'Playing'};
 if(n==='Stop')state={...state,state:'Stopped',active:false};
 return JSON.stringify({success:true,data});}}});
vm.runInContext(code,ctx);ctx.brookesia_app.on_start();
assert.match(texts['/main/status'],/未检测到 SD 卡/);
ctx.brookesia_app.on_action('toggle');assert.equal(calls.filter(c=>c.n==='Play').length,0);
mounted=true;tracks=[{path:'/sdcard/audiobooks/test/001.mp3',title:'001.mp3'},{path:'/sdcard/audiobooks/test/002.wav',title:'002.wav'}];
ctx.brookesia_app.on_action('scan');ctx.brookesia_app.on_action('toggle');assert.equal(state.path,tracks[0].path);
state.position=33;ctx.brookesia_app.on_timer();ctx.brookesia_app.on_action('toggle');assert.equal(state.state,'Paused');
assert.equal(JSON.parse(stored['/littlefs/audiobook-bookmark.json']).position,33);
ctx.brookesia_app.on_action('toggle');assert.equal(state.state,'Playing');
ctx.brookesia_app.on_pause();const count=calls.filter(c=>c.n==='GetState').length;ctx.brookesia_app.on_timer();assert.equal(calls.filter(c=>c.n==='GetState').length,count);
ctx.brookesia_app.on_resume();ctx.brookesia_app.on_action('next');assert.equal(state.path,tracks[1].path);assert.equal(state.position,0);
ctx.brookesia_app.on_stop();assert.equal(state.active,false);
vm.runInContext(code,ctx);ctx.brookesia_app.on_start();ctx.brookesia_app.on_action('toggle');assert.equal(state.path,tracks[1].path);
for(let i=0;i<30;i++)ctx.brookesia_app.on_action('louder');assert.equal(calls.filter(c=>c.n==='SetVolume').at(-1).a.Volume,100);
console.log('Audiobook regression passed: no card, playback/pause, bookmark, background, chapter change, volume bounds and retained context');
