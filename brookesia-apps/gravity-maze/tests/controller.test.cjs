const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),path=require('path');
const base=path.join(__dirname,'../src');const screen=JSON.parse(fs.readFileSync(base+'/res/screens/main.json')),paths=new Set();
function index(o,p=''){p+='/'+o.id;paths.add(p);(o.children||[]).forEach(c=>index(c,p));}index(screen);
let now=100000,lease=false,stale=false,asleep=false,stopCount=0,created=0,drawWrites=0,feature=true,theme='dark';const files={},texts={},events=[],calls=[],styles={};
class Clock extends Date{static now(){return now;}}
const ctx=vm.createContext({Date:Clock,brookesia:{start_service:n=>n,call_function(s,n,raw){const p=JSON.parse(raw);calls.push(n);let data=null;
 if(p.Path&&s==='SystemGui')assert(paths.has(p.Path),p.Path);
 if(n==='CreateView'){assert(paths.has(p.ParentPath));paths.add(p.ParentPath+'/'+p.InstanceId);created++;}
 if(n==='SetText')texts[p.Path]=p.Text;
 if(n==='SetBindings'){assert(p.Updates.length<=64);for(const u of p.Updates){assert(paths.has(u.Path),u.Path);styles[u.Path+':'+u.Key]=u.Value;if(u.Key==='draw'){drawWrites++;const commands=JSON.parse(u.Value);assert.equal(commands[0].type,'fill');assert(commands.length>=1);for(const c of commands){for(const key of ['x','y','width','height'])assert(Number.isInteger(c[key]),'Native canvas requires '+key+' even for fill');assert(c.width>0&&c.height>0);}for(const c of commands.slice(1))assert.equal(c.type,'rect');}}}
 if(n==='GetEnvironment')data={theme_id:theme};
 if(n==='FSReadText'){if(!files[p.Path])return JSON.stringify({success:false,error:'missing'});data=files[p.Path];}
 if(n==='FSWriteText')files[p.Path]=p.Data;
 if(n==='GetState')data=s==='ChildMode'?{enabled:true,allow_learning:true,resting:false,daily_minutes:0,remaining_seconds:0}:{screen_locked:false,screen_asleep:asleep,maze_canvas_cache:feature};
 if(n==='AcquireMotion'){assert(!lease);lease=true;data={token:4321};}
 if(n==='ReleaseMotion'){assert(lease);lease=false;}
 if(n==='ReadMotion'){assert(lease);data={available:true,sample_age_ms:stale||3,ax_g:0,ay_g:1,az_g:0,degrees:0};}
 if(n==='StartPeriodic'){assert(p.IntervalMs===33);data=9;}
 if(n==='Stop')stopCount++;
 if(n==='SubscribeAction')events.push(p.Action);
 return JSON.stringify({success:true,data});}}});
vm.runInContext('Array.from=undefined;',ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../engine.js'),'utf8')+'\n'+fs.readFileSync(path.join(__dirname,'../controller.js'),'utf8'),ctx);const app=ctx.brookesia_app;
function contrast(){
 function luminance(hex){const c=hex.slice(1).match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4));return .2126*c[0]+.7152*c[1]+.0722*c[2];}
 for(const [label,surface] of [['title',''],['status',''],['count',''],['start/label','start'],['hint/label','hint'],['pause/label','pause'],['finish/title','finish'],['finish/note','finish'],['finish/next/label','finish/next']]){
  const a=luminance(styles['/main/'+label+':ink']),b=luminance(styles['/main'+(surface?'/'+surface:'')+':bg']);
  assert((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=7,theme+' '+label+' has insufficient contrast');
 }
}
app.on_start();contrast();assert.equal(created,0,'Do not block on_start creating every wall');assert.deepEqual(events,['start','pause','hint','next']);app.on_action('start');assert(!lease,'Wait for map before acquiring motion');
for(let i=0;i<40;i++){const before=created;now+=33;app.on_timer();assert(created-before<=8,'Yield between batches of walls');if(JSON.parse(files['/sdcard/apps/local.gravitymaze/data/state.json']).mode==='ready')break;}
assert.equal(created,0,'Walls are cached in five fixed canvases');assert.equal(drawWrites,5);app.on_action('start');assert(lease);
for(let i=0;i<22;i++){now+=33;app.on_timer();}assert.equal(texts['/main/status'],'收集星星，沿通道找到小屋','Unlimited child time must remain playable');
assert.equal(drawWrites,5,'Movement never rebuilds the static maze');
app.on_action('hint');app.on_action('pause');assert(!lease);assert.equal(texts['/main/pause/label'],'继续');app.on_action('pause');assert(lease);
stale=400;now+=33;app.on_timer();assert(lease);assert.equal(texts['/main/status'],'感应恢复中，请轻轻拿稳');
stale=1200;now+=33;app.on_timer();assert(!lease);let report=JSON.parse(files['/sdcard/apps/local.gravitymaze/data/state.json']);assert.equal(report.mode,'paused');assert(report.error.includes('传感器'));
stale=false;app.on_action('start');asleep=true;now+=2000;app.on_timer();assert(!lease);assert(!calls.includes('Wake'),'Manual power and lock are never bypassed');
asleep=false;theme='light';app.on_resume();contrast();assert.equal(drawWrites,10,'A theme change rebuilds each canvas once');assert(!lease);app.on_action('start');app.on_pause();assert(!lease);app.on_stop();assert(stopCount>=3);assert(!calls.some(n=>/SetEnabled|SetRotation|Http|Connect/.test(n)));
assert.equal(JSON.parse(files['/sdcard/apps/local.gravitymaze/data/progress.json']).level,1);
feature=false;assert.throws(()=>app.on_start(),/配套固件/,'Unsupported firmware fails before showing a blank maze');
console.log('Controller: cached canvases, theme rebuilds, firmware guard, real view paths, calibration, stale sensor, unlimited child time, sleep and lease release passed.');

// Tile clipping must preserve every pixel, including the shared edges.
for(let k=0;k<40;k++){
 const commands=[{type:'fill',color:'#fff'}];
 for(let i=0;i<30;i++)commands.push({type:'rect',x:(i*73+k*17)%760-20,y:(i*91+k*13)%760-20,width:1+(i*47)%190,height:1+(i*31)%190,color:'#000'});
 for(let t=0;t<4;t++){
  const tx=(t%2)*360,ty=Math.floor(t/2)*360,tiled=ctx.tileCommands(commands,tx,ty,360);
  const hit=(cs,x,y)=>cs.slice(1).some(c=>x>=c.x&&x<c.x+c.width&&y>=c.y&&y<c.y+c.height);
  for(let n=0;n<600;n++){
   const x=n<3?[0,359,358][n]:(n*37+k*11)%360,y=(n*53+k*7)%360;
   assert.equal(hit(tiled,x,y),hit(commands,x+tx,y+ty));
  }
 }
}
console.log('Tile pixels match original rectangles at seams and random coordinates');
