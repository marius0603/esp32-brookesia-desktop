"""Authenticated LAN PCM gateway with playback acknowledgements and turn IDs."""
import asyncio,base64,hmac,json,struct,threading,time
from config_store import load
from conversation import Conversation
from deepseek_client import Cancelled
from engines import engines
from audio_diagnostics import capture_if_armed
from audio_wire import encode_adpcm,decode_packet

HEADER=struct.Struct('<4sII')
MAX_PCM=960000
state={'running':False,'connections':0,'recorded_bytes':0,'played_bytes':0,'last_error':''}

class Session:
    def __init__(self,ws):
        self.ws=ws;self.loop=asyncio.get_running_loop();self.conversation=Conversation()
        self.turn=0;self.recording=None;self.input_sequence=0;self.output_sequence=0
        self.ack_sequence=-1;self.sent_lengths={};self.ack=asyncio.Event();self.cancel=None;self.tasks=set();self.send_lock=asyncio.Lock()
        self.encoding='pcm_s16le';self.encode_state=(0,0)
    async def send(self,event):
        async with self.send_lock:await self.ws.send(json.dumps(event,ensure_ascii=False))
    def stop(self):
        self.conversation.cancel()
        if self.cancel:self.cancel.cancel()
        self.recording=None;self.ack.set()
    async def event(self,event,turn,cancel):
        if cancel.event.is_set() or self.turn!=turn:raise Cancelled()
        if event['type']!='audio':
            if 'text' in event:
                event=event|{'text':event['text'].encode('utf-8')[:1600 if event['type']!='user_text' else 600].decode('utf-8',errors='ignore')}
            return await self.send(event|{'turn':turn})
        pcm=event['pcm'];await self.send({'type':'audio_start','turn':turn,'text':event['text'],'sample_rate':16000})
        for at in range(0,len(pcm),1920):
            while self.output_sequence-self.ack_sequence>256:
                self.ack.clear()
                await asyncio.wait_for(self.ack.wait(),15)
                if cancel.event.is_set() or self.turn!=turn:raise Cancelled()
            if cancel.event.is_set() or self.turn!=turn:raise Cancelled()
            part=pcm[at:at+1920]
            if self.encoding=='ima_adpcm':packet,self.encode_state=encode_adpcm(part,turn,self.output_sequence,self.encode_state)
            else:packet=HEADER.pack(b'VPC1',turn,self.output_sequence)+part
            self.sent_lengths[self.output_sequence]=len(pcm[at:at+1920])
            self.output_sequence+=1
            async with self.send_lock:await self.ws.send(packet)
        await self.send({'type':'audio_end','turn':turn})
    async def run(self,turn,cancel,text=None,pcm=None):
        def emit(event):
            future=asyncio.run_coroutine_threadsafe(self.event(event,turn,cancel),self.loop)
            try:future.result(timeout=45)
            except BaseException:
                future.cancel();cancel.cancel();raise
        try:await asyncio.to_thread(self.conversation.run,text,pcm,emit,cancel)
        except Cancelled:pass
        except Exception as error:
            if not cancel.event.is_set() and self.turn==turn:
                state['last_error']=str(error)[:200]
                await self.send({'type':'error','turn':turn,'message':str(error)[:160]})
    def submit(self,text=None,pcm=None):
        self.cancel=self.conversation.begin()
        task=asyncio.create_task(self.run(self.turn,self.cancel,text,pcm));self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
    async def receive(self):
        hello=json.loads(await asyncio.wait_for(self.ws.recv(),10))
        config=load()
        if hello.get('type')!='hello' or not hmac.compare_digest(str(hello.get('token','')),config['device_token']):
            return await self.ws.close(1008,'Pairing required')
        if hello.get('sample_rate')!=16000:return await self.ws.close(1008,'PCM format mismatch')
        self.encoding=hello.get('encoding','pcm_s16le')
        if self.encoding not in ('pcm_s16le','ima_adpcm'):return await self.ws.close(1008,'Unsupported audio encoding')
        await self.send({'type':'status','state':'Preparing','message':'正在准备电脑模型'})
        if not engines.ready.is_set():
            task=asyncio.create_task(asyncio.to_thread(engines.warm))
            while not task.done():
                await self.send({'type':'status','state':'Preparing','message':'正在准备电脑模型'})
                await asyncio.sleep(2)
            await task
        await self.send({'type':'ready','message':'点击说话，再次点击发送','encoding':self.encoding})
        state['connections']+=1
        try:
            async for raw in self.ws:
                if isinstance(raw,bytes):
                    if self.recording is None or len(raw)<=HEADER.size:continue
                    turn,sequence,pcm=decode_packet(raw)
                    if turn!=self.turn:continue
                    if sequence!=self.input_sequence or len(pcm)%2 or len(pcm)>1920:raise ValueError('录音分片格式异常')
                    if len(self.recording)+len(pcm)>MAX_PCM:raise ValueError('录音超过30秒')
                    self.input_sequence+=1;self.recording.extend(pcm);state['recorded_bytes']+=len(pcm)
                    continue
                message=json.loads(raw);kind=message.get('type');turn=message.get('turn',0)
                if kind=='played' and turn==self.turn:
                    sequence=message.get('seq',-1)
                    if isinstance(sequence,int) and self.ack_sequence<sequence<self.output_sequence:
                        state['played_bytes']+=sum(self.sent_lengths.pop(n,0) for n in range(self.ack_sequence+1,sequence+1));self.ack_sequence=sequence;self.ack.set()
                elif kind in ('listen_start','text'):
                    if not isinstance(turn,int) or not 0<turn<2**32:raise ValueError('Invalid turn ID')
                    self.stop();self.turn=turn;self.output_sequence=0;self.ack_sequence=-1;self.sent_lengths={};self.input_sequence=0;self.encode_state=(0,0)
                    if kind=='listen_start':
                        self.recording=bytearray();await self.send({'type':'recording','turn':turn})
                    else:self.submit(text=str(message.get('text',''))[:1200])
                elif kind=='listen_end' and turn==self.turn and self.recording is not None:
                    pcm=bytes(self.recording);self.recording=None
                    try:
                        diagnostic=capture_if_armed(pcm)
                        if diagnostic:state['diagnostic']=diagnostic
                    except (OSError,ValueError) as error:
                        state['diagnostic']={'error':str(error)[:160]}
                    if len(pcm)<3200:await self.send({'type':'error','turn':turn,'message':'录音太短，请再说一次'})
                    else:self.submit(pcm=pcm)
                elif kind=='cancel':
                    self.stop();await self.send({'type':'cancelled','turn':self.turn})
        finally:self.stop();state['connections']-=1

async def handler(ws):
    config=load()
    if config.get('device_ip') and ws.remote_address[0] not in (config['device_ip'],'127.0.0.1','::1'):
        return await ws.close(1008,'Device address not paired')
    try:await Session(ws).receive()
    except Exception as error:
        state['last_error']=str(error)[:160]
        try:await ws.close(1011,'Connection interrupted')
        except Exception:pass

def start():
    def worker():
        import websockets.asyncio.server
        async def serve():
            async with websockets.asyncio.server.serve(handler,'127.0.0.1' if load().get('network_mode')!='lan' else '0.0.0.0',load().get('gateway_port',7861),max_size=8192,compression=None,ping_interval=20,ping_timeout=60):
                state['running']=True
                await asyncio.Future()
        try:asyncio.run(serve())
        except Exception as error:state['last_error']=str(error)[:160]
    threading.Thread(target=worker,daemon=True).start()
