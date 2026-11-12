// Offline deterministic random maze and bounded gravity physics.
var MazeCore=(function(){
'use strict';
function emptyGraph(n){const a=[];for(let i=0;i<n;i++)a.push([]);return a;}
const plans=[{"n":3,"route":[0,1,4,3,6,7,8],"branches":[[1,2],[2,5]],"stars":[1,3,7]},{"n":4,"route":[0,1,5,6,2,3,7,11,10,9,13,14,15],"branches":[[5,4],[4,8],[8,12]],"stars":[5,7,13]},{"n":5,"route":[0,1,6,5,10,15,20,21,16,11,12,7,8,13,18,23,24],"branches":[[23,22],[22,17],[24,19],[19,14],[14,9],[9,4],[4,3],[3,2]],"stars":[10,16,8]},{"n":6,"route":[0,6,7,13,19,25,31,32,33,34,28,27,26,20,21,15,9,10,11,17,23,29,35],"branches":[[23,22],[22,16],[11,5],[5,4],[4,3],[3,2],[2,8],[8,14],[2,1],[31,30],[30,24],[24,18],[18,12]],"stars":[25,27,10]},{"n":7,"route":[0,7,14,21,22,15,16,23,30,31,24,17,18,19,26,27,34,33,32,39,38,37,36,43,44,45,46,47,40,41,48],"branches":[[32,25],[43,42],[42,35],[35,28],[28,29],[27,20],[20,13],[13,12],[12,11],[11,10],[10,9],[9,8],[8,1],[1,2],[2,3],[3,4],[4,5],[5,6]],"stars":[23,27,43]},{"n":8,"route":[0,8,16,24,25,33,34,42,43,35,36,28,27,26,18,17,9,10,11,3,4,12,13,21,22,14,6,7,15,23,31,30,29,37,45,46,54,62,63],"branches":[[3,2],[2,1],[62,61],[61,53],[53,52],[52,44],[52,60],[60,59],[59,58],[58,50],[50,51],[50,49],[49,57],[57,56],[56,48],[48,40],[40,41],[40,32],[63,55],[55,47],[47,39],[39,38],[6,5],[21,20],[20,19]],"stars":[35,3,23]},{"n":9,"route":[0,1,2,11,10,9,18,19,20,21,22,13,14,5,6,15,24,25,34,35,44,53,52,61,60,59,58,49,50,51,42,41,32,31,30,39,38,47,56,57,66,67,76,77,78,69,70,71,80],"branches":[[35,26],[26,17],[17,8],[8,7],[7,16],[42,43],[32,33],[32,23],[39,40],[76,75],[75,74],[74,65],[65,64],[64,63],[63,72],[72,73],[63,54],[54,55],[55,46],[46,37],[37,36],[36,45],[36,27],[27,28],[28,29],[71,62],[80,79],[69,68],[57,48],[5,4],[4,3],[3,12]],"stars":[13,60,47]},{"n":10,"route":[0,10,20,30,40,50,51,61,71,81,91,92,82,72,62,52,42,41,31,21,11,12,22,32,33,34,35,36,37,38,48,49,59,69,79,78,77,67,68,58,57,47,46,56,55,65,66,76,86,85,75,74,73,83,84,94,95,96,97,98,99],"branches":[[49,39],[39,29],[29,19],[19,9],[9,8],[8,7],[7,6],[6,16],[16,17],[17,18],[18,28],[28,27],[27,26],[26,25],[25,24],[24,14],[14,4],[4,5],[5,15],[4,3],[3,13],[13,23],[3,2],[2,1],[73,63],[63,64],[64,54],[54,44],[44,45],[44,43],[43,53],[94,93],[99,89],[89,88],[88,87],[91,90],[90,80],[80,70],[70,60]],"stars":[62,48,66]},{"n":11,"route":[0,11,12,13,14,3,4,15,26,25,24,35,46,57,56,67,68,69,80,91,102,101,100,99,110,111,112,113,114,115,104,93,94,83,72,61,50,39,28,27,16,17,6,7,8,19,30,29,40,41,42,31,20,9,10,21,32,43,54,65,64,53,52,51,62,73,84,95,96,97,108,119,120],"branches":[[27,38],[38,37],[37,36],[36,47],[47,58],[58,59],[59,70],[70,81],[81,92],[92,103],[81,82],[82,71],[71,60],[60,49],[49,48],[29,18],[119,118],[118,107],[107,106],[106,105],[105,116],[116,117],[120,109],[109,98],[98,87],[87,76],[76,75],[75,86],[86,85],[85,74],[74,63],[6,5],[99,88],[88,89],[89,78],[78,79],[79,90],[78,77],[77,66],[66,55],[55,44],[44,33],[33,34],[34,23],[23,22],[34,45],[3,2],[2,1]],"stars":[69,50,21]},{"n":12,"route":[0,12,13,1,2,14,26,27,39,51,63,64,65,66,67,55,56,57,45,44,43,42,54,53,41,29,28,16,17,18,19,20,8,9,10,11,23,22,34,46,58,70,71,83,95,94,93,92,91,79,78,90,89,101,100,99,87,86,74,62,50,38,37,25,24,36,48,60,61,73,85,84,96,108,109,110,111,123,135,136,137,138,139,140,128,129,141,142,143],"branches":[[28,40],[40,52],[8,7],[7,6],[6,5],[5,4],[4,3],[3,15],[34,33],[33,32],[32,31],[31,30],[33,21],[79,80],[80,81],[81,69],[69,68],[81,82],[84,72],[143,131],[131,130],[130,118],[118,117],[117,105],[105,106],[106,107],[107,119],[105,104],[104,103],[103,115],[115,127],[127,126],[126,125],[125,113],[113,112],[112,124],[113,114],[114,102],[115,116],[135,134],[134,133],[133,132],[132,120],[120,121],[121,122],[110,98],[98,97],[61,49],[74,75],[75,76],[76,88],[76,77],[71,59],[59,47],[47,35]],"stars":[43,95,61]}];
 const bounds=[[5,9],[11,15],[17,21],[23,29],[31,37],[39,47],[49,59],[61,71],[73,85],[87,105]];

 function signature(p){const pairs=p.branches.concat(p.route.slice(1).map((b,i)=>[p.route[i],b]));return pairs.map(([a,b])=>Math.min(a,b)+':'+Math.max(a,b)).sort().join('|');}
 function generate(level,seed,previous){
  if(level<1||level>10||Math.floor(level)!==level)throw new Error("Invalid maze level");
  const size=level+2,[low,high]=bounds[level-1];let answer=null;
  for(let attempt=0;attempt<192;attempt++){
   let state=((seed+attempt*2654435761)>>>0)||1;
   const rand=max=>{state^=state<<13;state^=state>>>17;state^=state<<5;return (state>>>0)%max;};
   const seen=new Set([0]),stack=[0],all=[],graph=emptyGraph(size*size);
   while(stack.length){const a=stack[stack.length-1],r=Math.floor(a/size),c=a%size;
    const available=[r?a-size:-1,r<size-1?a+size:-1,c?a-1:-1,c<size-1?a+1:-1].filter(b=>b>=0&&!seen.has(b));
    if(!available.length){stack.pop();continue;}const b=available[rand(available.length)];seen.add(b);stack.push(b);all.push([a,b]);graph[a].push(b);graph[b].push(a);
   }
   const prev={0:-1},q=[0];for(let k=0;k<q.length;k++)for(const b of graph[q[k]])if(!(b in prev)){prev[b]=q[k];q.push(b);}
   const route=[];for(let i=size*size-1;i!==-1;i=prev[i])route.unshift(i);
   if(route.length<low||route.length>high)continue;
   const onPath=new Set(route.slice(1).map((b,i)=>Math.min(route[i],b)+':'+Math.max(route[i],b)));
   const count=route.length-2,stars=[];for(let j=0;j<3;j++){const begin=1+Math.floor(j*count/3),end=1+Math.floor((j+1)*count/3);stars.push(route[begin+rand(end-begin)]);}
   answer={n:size,route,branches:all.filter(([a,b])=>!onPath.has(Math.min(a,b)+':'+Math.max(a,b))),stars,seed};break;
  }
  // Finite generation time. A known-valid layout is the fallback, never an
  // unvalidated grid. Transpose preserves solvability and corner endpoints.
  if(!answer){const p=plans[level-1];answer={n:p.n,route:p.route.slice(),branches:p.branches.map(e=>e.slice()),stars:p.stars.slice(),seed:0};}
  if(signature(answer)===previous){const transpose=i=>(i%size)*size+Math.floor(i/size);answer.route=answer.route.map(transpose);answer.branches=answer.branches.map(e=>e.map(transpose));answer.stars=answer.stars.map(transpose);}
  return answer;
 }

 function build(level,seed,previous){
  const plan=generate(level,seed,previous),n=plan.n,cell=n<=6?324/n:60,world=n*cell,radius=n<=4?22:18;
  const edge={};function link(a,b){edge[Math.min(a,b)+':'+Math.max(a,b)]=true;}
  for(let i=1;i<plan.route.length;i++)link(plan.route[i-1],plan.route[i]);plan.branches.forEach(e=>link(e[0],e[1]));
  const walls=[[0,0,world,0],[0,0,0,world],[world,0,world,world],[0,world,world,world]];
  for(let r=0;r<n;r++)for(let c=0;c<n;c++){const a=r*n+c;if(c<n-1&&!edge[a+':'+(a+1)])walls.push([(c+1)*cell,r*cell,(c+1)*cell,(r+1)*cell]);if(r<n-1&&!edge[a+':'+(a+n)])walls.push([c*cell,(r+1)*cell,(c+1)*cell,(r+1)*cell]);}
  const center=i=>({x:(i%n+.5)*cell,y:(Math.floor(i/n)+.5)*cell});
  return {level,plan,n,cell,world,radius,walls,signature:signature(plan),x:cell/2,y:cell/2,vx:0,vy:0,stars:plan.stars.map(i=>Object.assign(center(i),{got:false})),goal:center(n*n-1),won:false};
 }
 function valid(m,x,y){for(let i=0;i<m.walls.length;i++){const w=m.walls[i],qx=Math.max(Math.min(w[0],w[2]),Math.min(Math.max(w[0],w[2]),x)),qy=Math.max(Math.min(w[1],w[3]),Math.min(Math.max(w[1],w[3]),y));if((x-qx)*(x-qx)+(y-qy)*(y-qy)<(m.radius+4)*(m.radius+4)-.001)return false;}return true;}
 function step(m,tx,ty,dt){
  if(m.won)return;dt=Math.max(0,Math.min(.05,dt));tx=Math.max(-1,Math.min(1,tx));ty=Math.max(-1,Math.min(1,ty));
  m.vx+=(tx*110-m.vx)*Math.min(1,dt*9);m.vy+=(ty*110-m.vy)*Math.min(1,dt*9);
  const steps=Math.max(1,Math.ceil(Math.max(Math.abs(m.vx*dt),Math.abs(m.vy*dt))/2));
  for(let i=0;i<steps;i++){const x=m.x+m.vx*dt/steps,y=m.y+m.vy*dt/steps;if(valid(m,x,m.y))m.x=x;else m.vx=0;if(valid(m,m.x,y))m.y=y;else m.vy=0;}
  for(let i=0;i<3;i++)if(Math.hypot(m.x-m.stars[i].x,m.y-m.stars[i].y)<32)m.stars[i].got=true;
  m.won=Math.hypot(m.x-m.goal.x,m.y-m.goal.y)<28;
 }
 function angles(s){let x=-s.ax_g,y=s.ay_g,z=s.az_g,t=x;
  // The panel rotation is relative to the saved upright calibration, whereas
  // acceleration is still in the IMU's factory axes. Include both rotations.
  const degrees=(s.degrees+(s.offset_degrees||0))%360;
  if(degrees===90){x=y;y=-t;}else if(degrees===180){x=-x;y=-y;}else if(degrees===270){x=-y;y=t;}
  return {roll:Math.atan2(x,Math.sqrt(y*y+z*z)),pitch:Math.atan2(y,z)};
 }
 function tilt(s,b){const a=angles(s),wrap=v=>Math.atan2(Math.sin(v),Math.cos(v)),axis=v=>{v=wrap(v)*180/Math.PI;return Math.abs(v)<3?0:Math.max(-1,Math.min(1,(v-Math.sign(v)*3)/17));};return {x:axis(a.roll-b.roll),y:axis(a.pitch-b.pitch)};}
 return {generate,build,valid,step,angles,tilt,bounds,signature};
})();
if(typeof module!=='undefined')module.exports=MazeCore;

(function(){
'use strict';
const ROOT='/sdcard/apps/local.gravitymaze/data/';
let gui,timer,sensor,storage,modes,audio,core,timerId=0,token=0,m=null,level=1,unlocked=1,mode='ready',background=false,lastTick=0,lastModes=0,frames=0,startMs=0,lastReport=0,wallCount=0,buildAt=0,buildTotal=0,building=false,signatures={},cache={},queue=[],dark=false,base=null,cal=[],hintCells=[],hintEnd=0,error='';
function call(h,n,a){const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(a||{})));if(!r.success)throw new Error(r.error||r.error_message||n);return r.data;}
function bind(path,key,value){value=String(value);const id=path+':'+key;if(cache[id]===value)return;cache[id]=value;queue.push({Path:'/main'+path,Key:key,Value:value});}
function flush(){if(!queue.length)return;const q=queue;queue=[];try{for(let i=0;i<q.length;i+=64)call(gui,'SetBindings',{Updates:q.slice(i,i+64)});}catch(e){cache={};throw e;}}
function text(id,value){const k='text:'+id;if(cache[k]===value)return;call(gui,'SetText',{Path:'/main/'+id,Text:value});cache[k]=value;}
function xy(path,x,y){bind(path,'x',Math.round(x));bind(path,'y',Math.round(y));}
function box(path,x,y,w,h){xy(path,x,y);bind(path,'w',Math.max(1,Math.round(w)));bind(path,'h',Math.max(1,Math.round(h)));}
function report(){try{call(storage,'FSWriteText',{Path:ROOT+'state.json',Data:JSON.stringify({version:'0.1.2',level,unlocked,mode,frames,elapsed_ms:Date.now()-startMs,wall_count:wallCount,lease:!!token,error,x:m?m.x:0,y:m?m.y:0,stars:m?m.stars.filter(s=>s.got).length:0,signature:m?m.signature:'',camera_follow:!!m&&m.n>6})});lastReport=Date.now();}catch(_){} }
function checkpoint(){try{call(storage,'FSWriteText',{Path:ROOT+'progress.json',Data:JSON.stringify({schema:1,level,unlocked,last_level:m?m.level:level,last_signature:m?m.signature:''})});}catch(_){} }
function cue(which){try{call(audio,'PlayGameCue',{Cue:which});}catch(_){} }
function release(){if(token){try{call(sensor,'ReleaseMotion',{Token:token});}catch(_){}token=0;}try{call(audio,'StopGameCue');}catch(_){} }
function stopTimer(){if(timerId){try{call(timer,'Stop',{TimerId:timerId});}catch(_){}timerId=0;} }
function startTimer(){if(!timerId)timerId=call(timer,'StartPeriodic',{Name:'gravity-maze',IntervalMs:33});lastTick=Date.now();}
function pause(message){mode='paused';release();stopTimer();if(m)m.vx=m.vy=0;text('status',message||'休息一下，小马会等你');text('pause/label','继续');text('start/label','校准继续');flush();report();}
function calibrate(){
 if(building)return;
 const state=call(modes,'GetState');if(state.screen_locked||state.screen_asleep){pause('请先解锁设备');return;}
 release();const lease=call(sensor,'AcquireMotion');token=lease.token;cal=[];base=null;mode='calibrating';error='';text('status','按舒服的角度拿稳，正在校准');text('pause/label','暂停');text('start/label','校准');startTimer();report();
}
function theme(){dark=call(core,'GetEnvironment').theme_id==='dark';bind('','bg',dark?'#1d2d33':'#fbf3e1');bind('/viewport','bg',dark?'#2e4542':'#eff1d7');
 for(const p of ['title','status','count','finish/title','finish/note','finish/next/label','start/label','hint/label','pause/label'])bind('/'+p,'ink',dark?'#fff4dc':'#392b23');
 for(const p of ['pause','hint','start','finish/next','viewport/map'])bind('/'+p,'bg',dark?'#35544a':'#e4ebcf');bind('/finish','bg',dark?'#1d2d33':'#fbf3e1');
 bind('/viewport/map/goal','bg',dark?'#fff4dc':'#392b23');
 for(let i=0;i<wallCount;i++)for(const parent of ['world','map'])bind('/viewport/'+parent+'/w'+i,'bg',dark?'#68927a':'#94b181');
}
function startLevel(){
 release();stopTimer();const seed=(Math.floor(Math.random()*2147483647)^Date.now())>>>0;m=MazeCore.build(level,seed,signatures[level]);signatures[level]=m.signature;mode='loading';error='';hintCells=[];hintEnd=0;building=true;buildAt=0;buildTotal=Math.max(wallCount,m.walls.length);
 bind('/viewport/world','hidden',true);bind('/viewport/map','hidden',true);bind('/finish','hidden',true);
 text('title','第'+level+'关 · '+m.n+'×'+m.n);text('count','星星 0 / 3');text('status','正在准备迷宫，请稍候');text('start/label','请稍候');text('pause/label','暂停');theme();flush();startTimer();report();
}
function buildStep(){
 const needed=m.walls.length,end=Math.min(buildTotal,buildAt+4);
 for(let i=buildAt;i<end;i++){
  if(i>=wallCount){for(const parent of ['world','map'])call(gui,'CreateView',{TemplateId:'maze_wall',ParentPath:'/main/viewport/'+parent,InstanceId:'w'+i});wallCount=i+1;}
  for(const parent of ['world','map']){const path='/viewport/'+parent+'/w'+i;bind(path,'hidden',i>=needed);if(i<needed){bind(path,'bg',dark?'#68927a':'#94b181');const w=m.walls[i],s=parent==='map'?68/m.world:1,pad=parent==='map'?4:0,width=parent==='map'?1:8;box(path,Math.min(w[0],w[2])*s-width/2+pad,Math.min(w[1],w[3])*s-width/2+pad,Math.abs(w[2]-w[0])*s+width,Math.abs(w[3]-w[1])*s+width);}}
 }
 buildAt=end;flush();if(buildAt<buildTotal)return;
 bind('/viewport/world','w',m.world);bind('/viewport/world','h',m.world);
 for(let i=0;i<3;i++)xy('/viewport/world/star'+i,m.stars[i].x-17,m.stars[i].y-17);
 box('/viewport/world/pony',m.x-m.radius,m.y-m.radius,m.radius*2,m.radius*2);xy('/viewport/world/home',m.goal.x-20,m.goal.y-20);
 xy('/viewport/map/goal',4+m.goal.x*68/m.world-2,4+m.goal.y*68/m.world-2);bind('/viewport/world','hidden',false);bind('/viewport/map','hidden',m.n<=6);
 building=false;mode='ready';stopTimer();text('status','轻轻倾斜，带小马回家');text('start/label','开始找家');render();checkpoint();report();
}
function route(at){const graph=[];for(let i=0;i<m.n*m.n;i++)graph.push([]);const pairs=m.plan.branches.slice();for(let i=1;i<m.plan.route.length;i++)pairs.push([m.plan.route[i-1],m.plan.route[i]]);pairs.forEach(e=>{graph[e[0]].push(e[1]);graph[e[1]].push(e[0]);});const q=[at],prev={};prev[at]=-1;for(let i=0;i<q.length;i++)for(const b of graph[q[i]])if(prev[b]===undefined){prev[b]=q[i];q.push(b);}const path=[];for(let k=m.n*m.n-1;k!==-1;k=prev[k])path.unshift(k);return path.slice(0,4);}
function render(){
 if(!m)return;const cx=Math.max(0,Math.min(m.world-324,m.x-162)),cy=Math.max(0,Math.min(m.world-324,m.y-162));xy('/viewport/world',-cx,-cy);xy('/viewport/world/pony',m.x-m.radius,m.y-m.radius);xy('/viewport/map/marker',4+m.x*68/m.world-3,4+m.y*68/m.world-3);
 for(let i=0;i<3;i++)bind('/viewport/world/star'+i,'hidden',m.stars[i].got);for(let i=0;i<4;i++){const at=hintCells[i],show=at!==undefined&&Date.now()<hintEnd;bind('/viewport/world/dot'+i,'hidden',!show);if(show)xy('/viewport/world/dot'+i,(at%m.n+.5)*m.cell-5,(Math.floor(at/m.n)+.5)*m.cell-5);}
 text('count','星星 '+m.stars.filter(s=>s.got).length+' / 3');flush();
}
function tick(){
 if(background)return;if(building){try{buildStep();}catch(e){error=String(e.message||e);pause('迷宫准备失败，请返回后重开');}return;}if(!token)return;const now=Date.now();
 try{
  if(now-lastModes>1000){lastModes=now;const state=call(modes,'GetState');if(state.screen_locked||state.screen_asleep){pause('休息一下，解锁后再继续');return;}const child=call(brookesia.start_service('ChildMode'),'GetState');if(child.enabled&&(!child.allow_learning||child.resting||(child.daily_minutes>0&&child.remaining_seconds===0))){pause('现在是家长设置的休息时间');return;} }
  const sample=call(sensor,'ReadMotion',{Token:token});if(!sample.available||sample.sample_age_ms<0||sample.sample_age_ms>1000)throw new Error('传感器数据暂不可用，请重新校准');
  if(sample.sample_age_ms>250){m.vx=m.vy=0;lastTick=now;if(mode==='calibrating')cal=[];text('status','感应恢复中，请轻轻拿稳');return;}
  const g=sample.ax_g*sample.ax_g+sample.ay_g*sample.ay_g+sample.az_g*sample.az_g;if(g<.55||g>1.65){if(mode==='calibrating')cal=[];m.vx=m.vy=0;lastTick=now;text('status','请轻轻拿稳，避免晃动');return;}
  if(mode==='calibrating'){cal.push(MazeCore.angles(sample));if(cal.length>=20){let sr=0,cr=0,sp=0,cp=0;cal.forEach(a=>{sr+=Math.sin(a.roll);cr+=Math.cos(a.roll);sp+=Math.sin(a.pitch);cp+=Math.cos(a.pitch);});base={roll:Math.atan2(sr,cr),pitch:Math.atan2(sp,cp)};mode='playing';text('status','收集星星，沿通道找到小屋');}lastTick=now;return;}
  if(mode!=='playing')return;const tilt=MazeCore.tilt(sample,base),before=m.stars.filter(s=>s.got).length;MazeCore.step(m,tilt.x,tilt.y,(now-lastTick)/1000);lastTick=now;frames++;const after=m.stars.filter(s=>s.got).length;
  if(after>before)cue(0);render();
  if(m.won){mode='won';stopTimer();release();unlocked=Math.max(unlocked,Math.min(10,level+1));text('finish/title',level===10?'十关全通，真棒！':'小马到家了！');text('finish/note','谢谢你陪它慢慢探索');text('finish/next/label',level===10?'从第一关再玩':'下一关 '+(level+3)+'×'+(level+3));bind('/finish','hidden',false);flush();checkpoint();cue(1);report();}
  else if(now-lastReport>10000)report();
 }catch(e){error=String(e.message||e);pause('暂时停一下，请点校准继续');}
}
globalThis.brookesia_app={
 on_start(){gui=brookesia.start_service('SystemGui');timer=brookesia.start_service('SystemTimer');sensor=brookesia.start_service('AutoRotation');storage=brookesia.start_service('Storage');modes=brookesia.start_service('DeviceModes');audio=brookesia.start_service('LearningAudio');core=brookesia.start_service('SystemCore');brookesia.start_service('ChildMode');background=false;cache={};startMs=Date.now();
  try{call(storage,'FSMkdir',{Path:ROOT});}catch(_){}
  try{const p=JSON.parse(call(storage,'FSReadText',{Path:ROOT+'progress.json'}));if(p.schema===1&&Number.isInteger(p.level)&&p.level>=1&&p.level<=10&&Number.isInteger(p.unlocked)&&p.unlocked>=p.level&&p.unlocked<=10){level=p.level;unlocked=p.unlocked;if(p.last_level===level&&typeof p.last_signature==='string'&&p.last_signature.length<4096)signatures[level]=p.last_signature;}}catch(_){}
  for(const Action of ['start','pause','hint','next'])call(gui,'SubscribeAction',{Action});startLevel();return true;},
 on_action(name){try{if(name==='start')calibrate();else if(name==='pause'){if(mode==='playing'||mode==='calibrating')pause();else if(mode==='paused')calibrate();}else if(name==='hint'&&m&&(mode==='playing'||mode==='ready')){hintCells=route(Math.floor(m.y/m.cell)*m.n+Math.floor(m.x/m.cell));hintEnd=Date.now()+4000;render();}else if(name==='next'&&mode==='won'){level=level===10?1:level+1;startLevel();}}catch(e){error=String(e.message||e);pause('暂不可用，请重新校准');}return true;},
 on_timer(){tick();return true;},
 on_pause(){background=true;release();stopTimer();mode='paused';checkpoint();report();return true;},
 on_resume(){background=false;cache={};theme();if(building){mode='loading';text('status','正在准备迷宫，请稍候');flush();startTimer();}else{pause('点校准继续，本局迷宫保持不变');render();}return true;},
 on_stop(){background=true;release();stopTimer();checkpoint();report();return true;}
};
})();
