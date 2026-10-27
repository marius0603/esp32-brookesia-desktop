"""Local browser front end sharing the resident speech model workers."""
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import base64, json, mimetypes, os, re, subprocess, threading, time, uuid
from urllib.parse import urlsplit
import web_extension
from engines import engines

ROOT=Path(__file__).resolve().parents[1]
PORT=7860
jobs={};lock=threading.Lock();pool=ThreadPoolExecutor(max_workers=1)

def ready():
    try:
        installed=json.loads((ROOT/'manifests/install-progress.json').read_text(encoding='utf-8')).get('complete',False)
        return installed and all((ROOT/'manifests'/('verified-'+name+'.json')).is_file()
            for name in ('Qwen3-TTS-12Hz-1.7B-CustomVoice','Qwen3-ASR-1.7B-hf'))
    except (OSError,ValueError):return False

def run_job(job_id,task,request):
    job_dir=ROOT/'outputs'/job_id
    job_dir.mkdir()
    if task=='asr':
        audio=base64.b64decode(request.pop('audio'),validate=True)
        if not audio or len(audio)>30*1024*1024:raise ValueError('录音文件需在 30MB 以内')
        suffix=Path(request.pop('filename','audio.wav')).suffix.lower()
        if suffix not in ('.wav','.mp3','.flac','.m4a','.ogg','.webm'):suffix='.wav'
        audio_path=job_dir/('录音'+suffix);audio_path.write_bytes(audio)
        request.update(input=str(audio_path),output=str(job_dir/'转写.txt'))
    else:request['output']=str(job_dir/'朗读.wav')
    path=job_dir/'request.json'
    path.write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
    with lock:jobs[job_id].update(state='running')
    env=os.environ.copy()
    env.update(TEMP=str(ROOT/'temp'),TMP=str(ROOT/'temp'),HF_HOME=str(ROOT/'cache/huggingface'),
        PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    if task=='tts':
        from worker import sections
        import wave
        audio=[];elapsed=0
        for section in sections(request['text']):
            part=engines.call('tts',request|{'op':'tts','text':section,'output':''})
            audio.append(base64.b64decode(part['pcm']));elapsed+=part['elapsed_seconds']
        pcm=b''.join(audio)
        with wave.open(request['output'],'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(pcm)
        data={'output':request['output'],'audio_seconds':len(pcm)/32000,'sample_rate':16000,'elapsed_seconds':elapsed}
    else:data=engines.call('asr',request|{'op':'asr'})
    path.with_suffix('.result.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    with lock:jobs[job_id].update(state='done',result=data,
        audio='/outputs/'+job_id+'/朗读.wav' if task=='tts' else None,
        download='/outputs/'+job_id+('/朗读.wav' if task=='tts' else '/转写.txt'))

def guarded_job(*args):
    try:run_job(*args)
    except Exception as error:
        with lock:jobs[args[0]].update(state='error',error=str(error))

class Handler(BaseHTTPRequestHandler):
    def send(self,status,data,mime='application/json; charset=utf-8'):
        if isinstance(data,(dict,list)):data=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers();self.wfile.write(data)
    def do_GET(self):
        path=urlsplit(self.path).path
        if web_extension.get(path,self):return
        if path=='/':return self.send(200,(ROOT/'scripts/index.html').read_bytes(),'text/html; charset=utf-8')
        if path=='/api/health':return self.send(200,{'app':'qwen-speech-local','ready':ready()})
        if path.startswith('/api/jobs/'):
            with lock:job=dict(jobs.get(path.rsplit('/',1)[1],{}))
            return self.send(200 if job else 404,job or {'error':'任务不存在'})
        if path.startswith('/outputs/'):
            from urllib.parse import unquote
            file=(ROOT/unquote(path.lstrip('/'))).resolve()
            if file.is_relative_to((ROOT/'outputs').resolve()) and file.is_file() and file.suffix in ('.wav','.txt'):
                return self.send(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        self.send(404,{'error':'未找到内容'})
    def do_POST(self):
        if self.headers.get('Origin') not in (None,'http://127.0.0.1:'+str(PORT),'http://localhost:'+str(PORT)):
            return self.send(403,{'error':'仅允许本机页面调用'})
        if web_extension.post(urlsplit(self.path).path,self):return
        task=urlsplit(self.path).path.removeprefix('/api/')
        if task not in ('tts','asr'):return self.send(404,{'error':'未知功能'})
        if not ready():return self.send(503,{'error':'模型正在准备，完成后即可使用。'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=42*1024*1024:raise ValueError('请求过大或为空')
            body=json.loads(self.rfile.read(length))
            if task=='tts':
                text=str(body.get('text','')).strip()
                if not 0<len(text)<=5000:raise ValueError('请输入 1–5000 个文字')
                body={key:str(body.get(key,default)) for key,default in [('text',text),('speaker','Vivian'),('instruct','温柔、清晰地朗读。')]}
                body['text']=text
            elif not isinstance(body.get('audio'),str):raise ValueError('请选择录音文件')
            else:body={key:body[key] for key in ('audio','filename') if key in body}
            job_id=uuid.uuid4().hex
            with lock:
                if sum(j['state'] in ('queued','running') for j in jobs.values())>=8:raise ValueError('已有多个任务，请稍后再试')
                jobs[job_id]={'id':job_id,'task':task,'state':'queued'}
            pool.submit(guarded_job,job_id,task,body)
            self.send(202,{'id':job_id})
        except (ValueError,KeyError) as error:self.send(400,{'error':str(error)})

if __name__=='__main__':
    web_extension.launch()
    ROOT.joinpath('logs/server.pid').write_text(str(os.getpid()),encoding='ascii')
    print('Qwen Speech: http://127.0.0.1:'+str(PORT),flush=True)
    ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
