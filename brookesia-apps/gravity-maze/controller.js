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
function report(){try{call(storage,'FSWriteText',{Path:ROOT+'state.json',Data:JSON.stringify({version:'0.1.5',level,unlocked,mode,frames,elapsed_ms:Date.now()-startMs,wall_count:wallCount,lease:!!token,error,x:m?m.x:0,y:m?m.y:0,stars:m?m.stars.filter(s=>s.got).length:0,signature:m?m.signature:'',camera_follow:!!m&&m.n>6,camera_x:m?m.cameraX:0,camera_y:m?m.cameraY:0})});lastReport=Date.now();}catch(_){} }
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
 if(!m)return;MazeCore.camera(m);xy('/viewport/world',-m.cameraX,-m.cameraY);xy('/viewport/world/pony',m.x-m.radius,m.y-m.radius);xy('/viewport/map/marker',4+m.x*68/m.world-3,4+m.y*68/m.world-3);
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
