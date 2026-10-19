(function () {
'use strict';
let gui,timer,storage,paused=false,shown=null,second=-1,flips=[],fx=0,started=0,frames=0,reported=false;
function call(h,n,a){const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(a||{})));if(!r.success)throw new Error(r.error||n);return r.data;}
function source(i,half,value){return (i<4?'big':'small')+'_'+half+'_'+value;}
function image(i,part,value,half){call(gui,'SetViewSrc',{Path:'/main/d'+i+'/'+part,Src:source(i,half,value)});}
function bind(i,key,value){return {Path:'/main/d'+i+'/flap',Key:key,Value:String(value)};}
function digits(now){if(now<1704067200000)return '----';const d=new Date(now+8*3600000);return String(d.getUTCHours()).padStart(2,'0')+String(d.getUTCMinutes()).padStart(2,'0');}
function height(i){return 75;}
function record(){try{call(storage,'FSWriteText',{Path:'/littlefs/clock-state.json',Data:JSON.stringify({version:1,time:Date.now(),digits:shown,frames,paused,timezone:'Asia/Shanghai'})});}catch(_){} }
function stopFx(){if(fx){try{call(timer,'Stop',{TimerId:fx});}catch(_){}fx=0;}}
function finish(){
  if(!flips.length){stopFx();return;}
  const updates=[];
  for(const f of flips){image(f.i,'bottom',f.next,'bottom');updates.push(bind(f.i,'opacity',0));}
  call(gui,'SetBindings',{Updates:updates});flips=[];stopFx();
  if(!reported&&frames>0){reported=true;record();}
}
function render(value){
  finish();const updates=[];
  for(let i=0;i<4;i++){image(i,'top',value[i],'top');image(i,'bottom',value[i],'bottom');updates.push(bind(i,'opacity',0));}
  call(gui,'SetBindings',{Updates:updates});shown=value;
}
function tick(){
  if(paused)return;const now=Date.now(),s=Math.floor(now/60000);if(s===second)return;
  const value=digits(now),sequential=s-second===1;second=s;
  if(shown===null||shown.includes('-')||value.includes('-')||!sequential){render(value);return;}
  finish();const updates=[];
  for(let i=0;i<4;i++)if(shown[i]!==value[i]){
    const h=height(i);flips.push({i,next:value[i],old:shown[i],half:0});
    image(i,'top',value[i],'top');image(i,'flap',shown[i],'top');
    updates.push(bind(i,'y',0),bind(i,'height',h),bind(i,'opacity',255));
  }
  shown=value;
  if(flips.length){call(gui,'SetBindings',{Updates:updates});started=now;fx=call(timer,'StartPeriodic',{Name:'flip',IntervalMs:40});}
}
function animate(){
  if(paused||!flips.length)return;const p=Math.max(0,(Date.now()-started)/360);frames++;
  if(p>=1){finish();return;}
  const updates=[];
  for(const f of flips){
    const h=height(f.i);
    if(p<.5){const visible=Math.max(1,Math.round(h*Math.cos(p*Math.PI)));updates.push(bind(f.i,'y',h-visible),bind(f.i,'height',visible));}
    else {if(!f.half){image(f.i,'flap',f.next,'bottom');f.half=1;}const visible=Math.max(1,Math.round(h*Math.sin((p-.5)*Math.PI)));updates.push(bind(f.i,'y',h+2),bind(f.i,'height',visible));}
  }
  call(gui,'SetBindings',{Updates:updates});
}
globalThis.brookesia_app={
  on_start(){gui=brookesia.start_service('SystemGui');timer=brookesia.start_service('SystemTimer');storage=brookesia.start_service('Storage');brookesia.start_service('SNTP');paused=false;tick();record();call(timer,'StartPeriodic',{Name:'clock',IntervalMs:250});return true;},
  on_timer(id,name){if(name==='flip')animate();else tick();return true;},
  on_pause(){finish();paused=true;stopFx();return true;},
  on_resume(){paused=false;second=-1;shown=null;reported=false;tick();record();return true;},
  on_stop(){paused=true;stopFx();flips=[];return true;}
};
})();
