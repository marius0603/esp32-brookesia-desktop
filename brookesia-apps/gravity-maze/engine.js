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
  // Broad phase: each cell stores only walls within the collision clearance.
  // Exact circle/segment tests below remain unchanged; no per-frame allocation.
  const collisionBounds=walls.map(w=>[Math.min(w[0],w[2]),Math.min(w[1],w[3]),Math.max(w[0],w[2]),Math.max(w[1],w[3])]),collisionBuckets=emptyGraph(n*n),clearance=radius+4;
  for(let i=0;i<collisionBounds.length;i++){
   const w=collisionBounds[i],c0=Math.max(0,Math.floor((w[0]-clearance)/cell)),c1=Math.min(n-1,Math.floor((w[2]+clearance)/cell)),r0=Math.max(0,Math.floor((w[1]-clearance)/cell)),r1=Math.min(n-1,Math.floor((w[3]+clearance)/cell));
   for(let r=r0;r<=r1;r++)for(let c=c0;c<=c1;c++)collisionBuckets[r*n+c].push(i);
  }
  return {level,plan,n,cell,world,radius,walls,collisionBounds,collisionBuckets,clearanceSquared:clearance*clearance-.001,cameraX:0,cameraY:0,signature:signature(plan),x:cell/2,y:cell/2,vx:0,vy:0,stars:plan.stars.map(i=>Object.assign(center(i),{got:false})),goal:center(n*n-1),won:false};
 }
 function valid(m,x,y){
  if(m.collisionBuckets){
   if(x<0||y<0||x>m.world||y>m.world)return false;
   const list=m.collisionBuckets[Math.min(m.n-1,Math.floor(y/m.cell))*m.n+Math.min(m.n-1,Math.floor(x/m.cell))];
   for(let i=0;i<list.length;i++){const w=m.collisionBounds[list[i]],qx=x<w[0]?w[0]:x>w[2]?w[2]:x,qy=y<w[1]?w[1]:y>w[3]?w[3]:y,dx=x-qx,dy=y-qy;if(dx*dx+dy*dy<m.clearanceSquared)return false;}
   return true;
  }
  for(let i=0;i<m.walls.length;i++){const w=m.walls[i],qx=Math.max(Math.min(w[0],w[2]),Math.min(Math.max(w[0],w[2]),x)),qy=Math.max(Math.min(w[1],w[3]),Math.min(Math.max(w[1],w[3]),y));if((x-qx)*(x-qx)+(y-qy)*(y-qy)<(m.radius+4)*(m.radius+4)-.001)return false;}return true;
 }
 function step(m,tx,ty,dt){
  // Keep short render delays from slowing the simulation to a crawl. Long
  // pauses remain capped, and collision travel is still split into <=2px steps.
  if(m.won)return;dt=Math.max(0,Math.min(.10,dt));tx=Math.max(-1,Math.min(1,tx));ty=Math.max(-1,Math.min(1,ty));
  m.vx+=(tx*120-m.vx)*Math.min(1,dt*16);m.vy+=(ty*120-m.vy)*Math.min(1,dt*16);
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
 function tilt(s,b){const a=angles(s),wrap=v=>Math.atan2(Math.sin(v),Math.cos(v)),axis=v=>{v=wrap(v)*180/Math.PI;return Math.abs(v)<=1.5?0:Math.max(-1,Math.min(1,(v-Math.sign(v)*1.5)/10.5));};return {x:axis(a.roll-b.roll),y:axis(a.pitch-b.pitch)};}
 function camera(m){
  if(m.world<=324){m.cameraX=m.cameraY=0;return;}
  // Restore continuous following: page jumps were less comfortable on screen.
  const limit=m.world-324;
  m.cameraX=Math.max(0,Math.min(limit,m.x-162));
  m.cameraY=Math.max(0,Math.min(limit,m.y-162));
 }
 return {generate,build,valid,step,angles,tilt,camera,bounds,signature};
})();
if(typeof module!=='undefined')module.exports=MazeCore;
