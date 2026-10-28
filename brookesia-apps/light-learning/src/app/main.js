(function(){
'use strict';
const ROOT='/sdcard/learning/packs/',kinds=['cards','arithmetic','english'];
const names={cards:'动物卡片',arithmetic:'口算',english:'英语跟读'};
let gui,audio,storage,modes,speaker,timer,timerId=0,hidden=false,cache={},catalog=[],pack=null,packIndex=0,mode='home',index=0,flipped=false,feedback='',audioState={},pending=null,lastSwipe=0;
function call(h,n,args){const r=JSON.parse(brookesia.call_function(h,n,JSON.stringify(args||{}),h===audio?6000:3000));if(!r.success)throw new Error(r.error||r.error_message||n);return r.data;}
function text(path,value){value=String(value===undefined?'':value);if(hidden||cache[path]===value)return;call(gui,'SetText',{Path:'/main/'+path,Text:value});cache[path]=value;}
function bind(path,key,value){const k=path+':'+key;value=String(value);if(hidden||cache[k]===value)return;call(gui,'SetBinding',{Path:'/main/'+path,Key:key,Value:value});cache[k]=value;}
function validText(v,max){return typeof v==='string'&&v.length>0&&v.length<=max&&!/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(v);}
function mediaPath(v){return typeof v==='string'&&v.length<=96&&/^[a-z0-9][a-z0-9_.\/-]*\.wav$/.test(v)&&v.split('/').every(p=>p&&p!=='.'&&p!=='..');}
function imagePath(v){return typeof v==='string'&&v.endsWith('.png')&&mediaPath(v.slice(0,-4)+'.wav');}
function ensure(ok,message){if(!ok)throw new Error(message);}
function validateIndex(data){
 ensure(data&&data.schema===1&&Array.isArray(data.packs)&&data.packs.length>0&&data.packs.length<=16,'内容包目录格式不正确');
 const seen=new Set();
 for(const p of data.packs){ensure(p&&typeof p.id==='string'&&/^[a-z0-9][a-z0-9_-]{0,31}$/.test(p.id)&&validText(p.title,12)&&!seen.has(p.id),'内容包名称或编号不正确');seen.add(p.id);}
 return data.packs;
}
function validatePack(data,id){
 ensure(data&&data.schema===1&&data.id===id&&validText(data.title,12),'内容包编号或版本不正确');let total=0;
 for(const kind of kinds){ensure(Array.isArray(data[kind])&&data[kind].length<=128,'内容分类格式不正确');total+=data[kind].length;}
 ensure(total>0,'内容包是空的');
 for(const c of data.cards)ensure(c&&validText(c.name,6)&&validText(c.pinyin,32)&&validText(c.english,20)&&imagePath(c.image)&&mediaPath(c.audio),'动物卡片格式不正确');
 for(const q of data.arithmetic){
  ensure(q&&Number.isInteger(q.a)&&Number.isInteger(q.b)&&q.a>=0&&q.a<=100&&q.b>=0&&q.b<=100&&['+','-'].includes(q.operator),'口算题格式不正确');
  const answer=q.operator==='+'?q.a+q.b:q.a-q.b;
  ensure(answer>=0&&q.answer===answer&&Array.isArray(q.choices)&&q.choices.length===3&&new Set(q.choices).size===3&&q.choices.every(n=>Number.isInteger(n)&&n>=0&&n<=200)&&q.choices.includes(answer),'口算答案与题目不一致');
 }
 for(const c of data.english)ensure(c&&validText(c.text,24)&&validText(c.meaning,12)&&mediaPath(c.audio)&&Number.isInteger(c.record_seconds)&&c.record_seconds>=1&&c.record_seconds<=8,'英语卡格式不正确');
 return data;
}
function readJson(path,max){const raw=call(storage,'FSReadText',{Path:path});ensure(typeof raw==='string'&&raw.length<=max,'内容文件过大或不可读取');return JSON.parse(raw);}
function loadCatalog(){
 try{catalog=validateIndex(readJson('/sdcard/learning/index.json',8192));packIndex=Math.min(packIndex,catalog.length-1);loadPack(packIndex);}
 catch(e){catalog=[];pack=null;text('home/status','未找到可用内容包');}
 call(gui,'SetBinding',{Path:'/main/home/pack',Key:'options',Value:JSON.stringify(catalog.length?catalog.map(p=>p.title):['暂无内容包'])});
}
function loadPack(selected){
 ensure(Number.isInteger(selected)&&selected>=0&&selected<catalog.length,'请选择有效内容包');
 const entry=catalog[selected],next=validatePack(readJson(ROOT+entry.id+'/pack.json',49152),entry.id);
 discard();pack=next;packIndex=selected;index=0;mode='home';cache={};
 bind('home/pack','selected',selected);render();
}
function current(){return pack&&mode!=='home'?pack[mode][index]:null;}
function discard(){pending=null;try{call(audio,'Discard');}catch(_){}audioState={};feedback='';}
function queueAudio(fn,args){
 const s=call(audio,'GetState')||{};
 if(s.active){pending={fn,args};call(audio,'Stop');}
 else call(audio,fn,args);
 poll();
}
function playSample(){const item=current();if(item&&item.audio)queueAudio('PlayFile',{Path:ROOT+pack.id+'/'+item.audio});}
function render(){
 bind('home','hidden',mode!=='home');bind('lesson','hidden',mode==='home');
 if(mode==='home'){
  text('home/status',pack?pack.title+' · 一起轻松学':'未找到可用内容包');
  for(const kind of kinds)text('home/'+kind+'/count',pack?pack[kind].length+' '+(kind==='cards'?'张':kind==='english'?'句':'题'):'--');
  return;
 }
 const c=current();if(!c)return;
 text('lesson/header/title',names[mode]);text('lesson/header/count',(index+1)+' / '+pack[mode].length);
 let prompt='',detail='',size=48,buttons=[];
 if(mode==='cards'){prompt=c.name;detail=c.pinyin+' · '+c.english;size=34;buttons=['听名字','',''];}
 else if(mode==='arithmetic'){prompt=c.a+' '+(c.operator==='-'?'−':'+')+' '+c.b+' = ?';size=46;buttons=c.choices;}
  else {prompt=c.text;detail=c.meaning;size=c.text.length>12?30:38;buttons=['听示范',audioState.state==='Recording'?'结束':audioState.state==='Starting'?'准备中':'录音','回放'];}
 bind('lesson/card','hidden',mode==='cards');bind('lesson/animalCard','hidden',mode!=='cards');bind('lesson/actions','hidden',mode==='cards');bind('lesson/nav','hidden',mode==='cards');bind('lesson/readName','hidden',mode!=='cards');
 if(mode==='cards'){text('lesson/animalCard/name',c.name);text('lesson/animalCard/caption',detail);const src=ROOT+pack.id+'/'+c.image;if(cache.image!==src){call(gui,'SetViewSrc',{Path:'/main/lesson/animalCard/picture',Src:src});cache.image=src;}}
 text('lesson/card/prompt',prompt);bind('lesson/card/prompt','size',size);text('lesson/card/detail',detail);
 for(let i=0;i<3;i++)text('lesson/actions/a'+i+'/label',buttons[i]);
 text('lesson/nav/center/label',mode==='cards'?'听名字':mode==='english'?'随机一句':'随机一题');
 bind('lesson/feedback','y',mode==='cards'?368:344);text('lesson/feedback',feedback);
}
function choose(kind){ensure(pack&&kinds.includes(kind)&&pack[kind].length>0,'这个包还没有这类内容');discard();mode=kind;index=0;flipped=false;render();if(mode==='cards')playSample();}
function move(delta){if(!current())return;discard();index=(index+delta+pack[mode].length)%pack[mode].length;flipped=false;render();if(mode==='cards')playSample();}
function answer(at){
 const c=current();if(!c)return;
 if(mode==='cards'){playSample();
 }else if(mode==='arithmetic'){
  const correct=c.choices[at]===c.answer;feedback=correct?'答对了！':'再试一次';render();
 }else if(mode==='english'){
  if(at===0)playSample();
  else if(at===1){
   const s=call(audio,'GetState')||{};
   if(s.state==='Starting')return;
   if(s.state==='Recording')call(audio,'StopRecording');
   else queueAudio('StartRecording',{Seconds:c.record_seconds});
  }else queueAudio('Replay');
 }
}
function poll(){
 if(hidden)return;
 audioState=call(audio,'GetState')||{};
 if(pending&&!audioState.active){const request=pending;pending=null;call(audio,request.fn,request.args);audioState=call(audio,'GetState')||{};}
 if(mode==='english'){
  if(audioState.error)feedback=audioState.error;
  else if(audioState.state==='Recording')feedback='跟读中 '+((audioState.recorded_ms||0)/1000).toFixed(1)+' 秒';
  else if(audioState.state==='Recorded')feedback='录音好了，可以回放';
  else if(audioState.state==='Playing')feedback='播放中';
  else if(audioState.recorded_bytes)feedback='录音已保留';
 }else if(audioState.error&&mode!=='home')feedback=audioState.error;
 render();
 const sound=call(modes,'GetState'),vol=call(speaker,'GetVolume');
 text('home/volume',sound.do_not_disturb?'音量 '+sound.resume_volume+'% · 静音':'音量 '+vol+'%');
}
function action(name,path,payload){
 if(name==='cardSwipe'&&mode==='cards'){let value;try{value=typeof payload==='string'?JSON.parse(payload):payload;}catch(_){return;}if(!value||!['left','right'].includes(value.direction))return;const now=Date.now();if(now-lastSwipe<250)return;lastSwipe=now;move(value.direction==='left'?1:-1);return;}
 if((name==='readName'||name==='cardTap')&&mode==='cards'){if(Date.now()-lastSwipe>=300)playSample();return;}
 if(kinds.includes(name)){choose(name);return;}
 if(name==='back'){discard();mode='home';render();return;}
 if(name==='previous'){move(-1);return;}if(name==='next'){move(1);return;}
 if(name==='center'){
  if(mode==='cards')playSample();
  else if(current()&&pack[mode].length>1)move(1+Math.floor(Math.random()*(pack[mode].length-1)));
  return;
 }
 if(/^a[0-2]$/.test(name)){answer(Number(name.slice(1)));return;}
 if(name==='pack'){
  const raw=call(gui,'GetBinding',{Path:'/main/home/pack',Key:'selected'});
  ensure(typeof raw==='string'&&/^\d+$/.test(raw),'请选择有效内容包');loadPack(Number(raw));
 }
}
globalThis.brookesia_app={
 on_start(){
  hidden=false;cache={};mode='home';gui=brookesia.start_service('SystemGui');storage=brookesia.start_service('Storage');audio=brookesia.start_service('LearningAudio');modes=brookesia.start_service('DeviceModes');speaker=brookesia.start_service('AudioPlayback');timer=brookesia.start_service('SystemTimer');
  for(const [service,fn] of [['Audiobook','Stop'],['LocalVoice','Disconnect'],['VoiceAssistant','Disconnect']])try{call(brookesia.start_service(service),fn);}catch(_){}
  for(const name of kinds.concat(['back','previous','next','center','a0','a1','a2','pack','cardSwipe','cardTap','readName']))call(gui,'SubscribeAction',{Action:name});
  loadCatalog();render();timerId=call(timer,'StartPeriodic',{Name:'light-learning',IntervalMs:250});return true;
 },
 on_action(name,path,payload){try{action(name,path,payload);}catch(e){feedback=String(e.message||e);text(mode==='home'?'home/status':'lesson/feedback',feedback);}return true;},
 on_timer(){if(!hidden)try{poll();}catch(e){text(mode==='home'?'home/status':'lesson/feedback',String(e.message||e));}return true;},
 on_pause(){discard();hidden=true;return true;},
 on_resume(){hidden=false;cache={};mode='home';loadCatalog();render();return true;},
 on_stop(){discard();try{if(timerId)call(timer,'Stop',{TimerId:timerId});}catch(_){}timerId=0;hidden=true;return true;}
};
})();
