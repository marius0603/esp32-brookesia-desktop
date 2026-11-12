const assert=require('node:assert/strict'),M=require('../engine.js');
let total=0;
for(let level=1;level<=10;level++){
 let signature='';
 for(let round=1;round<=40;round++){
  const m=M.build(level,round*73141+level,signature),p=m.plan,n=m.n,edges=p.branches.concat(p.route.slice(1).map((b,i)=>[p.route[i],b])),graph=Array.from({length:n*n},()=>[]);
  assert.notEqual(m.signature,signature);signature=m.signature;assert.equal(edges.length,n*n-1);
  for(const [a,b] of edges){assert.equal(Math.abs(a%n-b%n)+Math.abs(Math.floor(a/n)-Math.floor(b/n)),1);graph[a].push(b);graph[b].push(a);}
  const seen=new Set([0]),q=[0];for(let i=0;i<q.length;i++)for(const b of graph[q[i]])if(!seen.has(b)){seen.add(b);q.push(b);}assert.equal(seen.size,n*n);
  assert(p.route.length>=M.bounds[level-1][0]&&p.route.length<=M.bounds[level-1][1]);assert.equal(new Set(p.stars).size,3);p.stars.forEach(i=>assert(p.route.slice(1,-1).includes(i)));
  if(round===1){
   for(let i=0;i<300;i++)M.step(m,-1,0,.05);assert(m.x>=m.radius+4-.01,'Outer wall is solid');
   for(const at of p.route){const gx=(at%n+.5)*m.cell,gy=(Math.floor(at/n)+.5)*m.cell;let reached=false;
    for(let i=0;i<1000;i++){const dx=gx-m.x,dy=gy-m.y;if(Math.hypot(dx,dy)<3||m.won){reached=true;break;}M.step(m,Math.max(-1,Math.min(1,dx/25)),Math.max(-1,Math.min(1,dy/25)),i%3===0?.1:.033);assert(M.valid(m,m.x,m.y),'No corner tunnelling with delayed frames');}assert(reached,'Exit path is traversable: '+JSON.stringify({level,at,gx,gy,x:m.x,y:m.y,vx:m.vx,vy:m.vy}));if(m.won)break;
   }
   assert(m.won);assert(m.stars.every(s=>s.got));
  }
  total++;
 }
}
assert.throws(()=>M.build(0,1,''));assert.throws(()=>M.build(11,1,''));
const upright={ax_g:0,ay_g:1,az_g:0,degrees:0},base=M.angles(upright);assert.equal(M.tilt(upright,base).x,0);assert.equal(M.tilt(upright,base).y,0);
assert(M.tilt({ax_g:-.342,ay_g:.94,az_g:0,degrees:0},base).x>.9);
assert(M.tilt({ax_g:0,ay_g:.94,az_g:-.342,degrees:0},base).y>.9);
assert(M.tilt({ax_g:0,ay_g:.94,az_g:.342,degrees:0},base).y<-.9);
function rolled(deg){const a=deg*Math.PI/180;return M.tilt({ax_g:-Math.sin(a),ay_g:Math.cos(a),az_g:0,degrees:0},base).x;}
assert.equal(rolled(1),0,'Small hand tremor remains inside dead zone');
assert(rolled(2)>0&&rolled(4)>.23,'Gentle tilts start moving without a large wrist turn');
assert(rolled(12)>.99,'Full response at a comfortable tilt');
assert(Math.abs(rolled(-4)+rolled(4))<1e-10);
const field=()=>({won:false,x:0,y:0,vx:0,vy:0,walls:[],radius:18,stars:[{x:999,y:999},{x:999,y:999},{x:999,y:999}],goal:{x:999,y:999}});
const quick=field();M.step(quick,1,0,.033);assert(quick.vx>50&&quick.x>1.5,'Prompt start');M.step(quick,0,0,.033);assert(quick.vx<35,'Prompt stop');
const delayed=field();M.step(delayed,1,0,.1);assert(delayed.x>10&&delayed.x<=12,'A short render delay retains elapsed movement');
const gap=field();M.step(gap,1,0,5);assert(gap.x<=12,'A long pause never becomes an uncontrolled jump');
// Saved board mounting offsets and live panel rotation must both participate.
// Transform the same physical screen-space tilt back to each factory IMU pose.
for(const degrees of [0,90,180,270])for(const offset_degrees of [0,90,180,270]){
 function sample(x,y,z){const turn=(degrees+offset_degrees)%360;let rawX=x,rawY=y;
  if(turn===90){rawX=-y;rawY=x;}else if(turn===180){rawX=-x;rawY=-y;}else if(turn===270){rawX=y;rawY=-x;}
  return {ax_g:-rawX,ay_g:rawY,az_g:z,degrees,offset_degrees};}
 const zero=M.angles(sample(0,1,0));
 assert(M.tilt(sample(.342,.94,0),zero).x>.9);
 assert(M.tilt(sample(-.342,.94,0),zero).x<-.9);
 assert(M.tilt(sample(0,.94,-.342),zero).y>.9);
 assert(M.tilt(sample(0,.94,.342),zero).y<-.9);
 assert(Math.abs(M.tilt(sample(.342,.94,0),zero).y)<.001);
}
console.log(total+' random maps: connected trees, difficulty ranges, no consecutive repeats, stars, ten physics paths, bounds and upright pitch passed.');
