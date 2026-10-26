from pathlib import Path
import base64,json,os,queue,subprocess,threading,time,uuid
from config_store import ROOT

class Worker:
    def __init__(self,kind):self.kind=kind;self.process=None;self.lock=threading.RLock();self.results=queue.Queue();self.log=None
    def start(self):
        if self.process and self.process.poll() is None:return
        self.results=queue.Queue()
        env=os.environ.copy();env.update(QWEN_SPEECH_ROOT=str(ROOT),PYTHONUTF8='1',PYTHONIOENCODING='utf-8',TEMP=str(ROOT/'temp'),TMP=str(ROOT/'temp'))
        self.log=(ROOT/'logs'/('resident-'+self.kind+'.log')).open('a',encoding='utf-8')
        self.process=subprocess.Popen([str(ROOT/'envs'/self.kind/'Scripts/python.exe'),'-X','utf8',str(ROOT/'scripts/engine_worker.py'),'--kind',self.kind],
            cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,encoding='utf-8',bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW)
        process=self.process;results=self.results
        def read():
            for line in process.stdout:
                try:results.put(json.loads(line))
                except ValueError:continue
            results.put({'ok':False,'error':'Model worker exited'})
        threading.Thread(target=read,daemon=True).start()
    def call(self,request,timeout=180):
        with self.lock:
            self.start();identifier=uuid.uuid4().hex
            self.process.stdin.write(json.dumps(request|{'id':identifier},ensure_ascii=False)+'\n');self.process.stdin.flush()
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                try:response=self.results.get(timeout=min(2,max(.1,deadline-time.monotonic())))
                except queue.Empty:continue
                if not response.get('ok'):raise RuntimeError(response.get('error','Model failure'))
                if response.get('id')==identifier:return response['result']
            raise TimeoutError('Model processing timed out')

class Engines:
    def __init__(self):
        self.workers={name:Worker(name) for name in ('asr','tts')}
        self.gpu=threading.RLock();self.ready=threading.Event();self.error='';self.loading=False
    def warm(self):
        with self.gpu:
            if self.ready.is_set():return
            self.loading=True
            try:
                for worker in self.workers.values():worker.call({'op':'load'})
                self.ready.set();self.error=''
            except Exception as error:self.error=str(error);raise
            finally:self.loading=False
    def call(self,kind,request):
        with self.gpu:
            self.warm()
            return self.workers[kind].call(request)
    def close(self):
        for worker in self.workers.values():
            if worker.process and worker.process.poll() is None:worker.process.terminate()

engines=Engines()
