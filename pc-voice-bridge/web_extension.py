from pathlib import Path
import base64,json,threading,uuid,wave
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from config_store import ROOT,load,save,public,set_key
from engines import engines
from conversation import Conversation
from deepseek_client import Cancelled
import device_gateway
import public_tunnel

jobs={};lock=threading.RLock();conversation=Conversation();pool=ThreadPoolExecutor(max_workers=1)

def launch():
    device_gateway.start()
    public_tunnel.start()
    def warm():
        try:engines.warm()
        except Exception:pass
    threading.Thread(target=warm,daemon=True).start()

def get(path,handler):
    if path=='/assistant':handler.send(200,(ROOT/'scripts/assistant.html').read_bytes(),'text/html; charset=utf-8');return True
    if path=='/api/assistant/state':
        handler.send(200,{'config':public(),'models_ready':engines.ready.is_set(),'loading':engines.loading,
            'model_error':engines.error,'gateway':dict(device_gateway.state),'tunnel':dict(public_tunnel.state)});return True
    if path.startswith('/api/assistant/jobs/'):
        job=serializable_job(path.rsplit('/',1)[1])
        handler.send(200 if job else 404,job or {'error':'任务不存在'});return True
    return False

def post(path,handler):
    if path not in ('/api/assistant/config','/api/assistant/chat','/api/assistant/cancel'):return False
    try:
        length=int(handler.headers.get('Content-Length','0'))
        if not 0<length<42*1024*1024:raise ValueError('请求大小异常')
        data=json.loads(handler.rfile.read(length))
        if path.endswith('/config'):
            config=load()
            if 'base_url' in data:
                url=str(data['base_url']).rstrip('/');parts=urlsplit(url)
                if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
                    raise ValueError('请输入有效的 API 地址')
                config['base_url']=url
            if 'model' in data:config['model']=str(data['model'])[:120]
            if 'speaker' in data:
                if data['speaker'] not in ('Serena','Vivian','Uncle_Fu'):raise ValueError('请选择有效声音')
                config['speaker']=data['speaker']
            save(config)
            if data.get('api_key'):set_key(str(data['api_key']))
            handler.send(200,{'saved':True,'config':public()});return True
        if path.endswith('/cancel'):
            with lock:
                job=jobs.get(str(data.get('id','')))
                if job and job['state'] in ('queued','running'):
                    job['cancel'].cancel();job['state']='cancelled'
            handler.send(200,{'cancelled':True});return True
        if not load().get('api_key_dpapi'):raise ValueError('请先配置云服务密钥')
        if not engines.ready.is_set():raise ValueError('模型正在准备，请稍后再试')
        text=str(data.get('text','')).strip()
        audio=data.get('audio')
        if not audio and not 0<len(text)<=1200:raise ValueError('请输入文字或录音')
        identifier=uuid.uuid4().hex
        cancel=conversation.begin()
        with lock:
            for previous in jobs.values():
                if previous['state'] in ('queued','running'):previous['state']='cancelled';previous['cancel'].cancel()
            jobs[identifier]={'id':identifier,'state':'queued','answer':'','user_text':'','audios':[],'cancel':cancel}
        pool.submit(run,identifier,text,data,cancel)
        handler.send(202,{'id':identifier})
    except (ValueError,KeyError) as error:handler.send(400,{'error':str(error)})
    return True

def run(identifier,text,data,cancel):
    folder=ROOT/'outputs'/identifier;folder.mkdir()
    def event(message):
        cancel.check();kind=message['type']
        with lock:
            job=jobs[identifier]
            if kind=='status':job['message']=message['message']
            elif kind=='user_text':job['user_text']=message['text'];job['language']=message.get('language','')
            elif kind=='answer':job['answer']=message['text']
            elif kind=='audio':
                name=str(len(job['audios']))+'.wav';target=folder/name
                with wave.open(str(target),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(message['pcm'])
                job['audios'].append('/outputs/'+identifier+'/'+name)
            elif kind=='done':job['answer']=message['text']
    try:
        with lock:jobs[identifier]['state']='running'
        cancel.check()
        if data.get('audio'):
            raw=base64.b64decode(data['audio'],validate=True)
            if not 0<len(raw)<=30*1024*1024:raise ValueError('录音文件需在30MB以内')
            suffix=Path(str(data.get('filename','录音.webm'))).suffix.lower()
            if suffix not in ('.wav','.webm','.mp3','.m4a','.ogg','.flac'):raise ValueError('不支持的录音格式')
            source=folder/('录音'+suffix);source.write_bytes(raw)
            event({'type':'status','message':'正在识别'})
            result=engines.call('asr',{'op':'asr','input':str(source)})
            cancel.check();text=result['text'].strip()
        conversation.run(text=text,emit=event,cancel=cancel)
        with lock:jobs[identifier]['state']='done'
    except Cancelled:
        with lock:jobs[identifier]['state']='cancelled'
    except Exception as error:
        with lock:jobs[identifier].update(state='error',error=str(error)[:200])

def serializable_job(identifier):
    with lock:return {k:v for k,v in jobs.get(identifier,{}).items() if k!='cancel'}
