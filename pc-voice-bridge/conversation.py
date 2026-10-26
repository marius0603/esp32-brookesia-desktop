from concurrent.futures import ThreadPoolExecutor
import base64,queue,threading,time
from config_store import load
from engines import engines
from deepseek_client import Cancellation,Cancelled,stream_answer,messages,take_sentences

class Conversation:
    def __init__(self):self.history=[];self.lock=threading.Lock();self.current=None
    def cancel(self):
        with self.lock:
            if self.current:self.current.cancel()
    def begin(self):
        with self.lock:
            if self.current:self.current.cancel()
            self.current=Cancellation()
            return self.current
    def run(self,text=None,pcm=None,emit=lambda event:None,cancel=None):
        cancel=cancel or self.begin()
        cancel.check()
        def event(kind,**data):cancel.check();emit({'type':kind,**data})
        try:
            event('status',state='Preparing',message='正在准备语音模型')
            engines.warm();cancel.check()
            if pcm is not None:
                event('status',state='Recognizing',message='正在识别')
                result=engines.call('asr',{'op':'asr','pcm':base64.b64encode(pcm).decode()})
                text=result['text'].strip();event('user_text',text=text,language=result.get('language',''))
            else:text=(text or '').strip();event('user_text',text=text,language='')
            if not text:raise ValueError('没有听清楚，请再说一次')
            event('status',state='Thinking',message='正在思考')
            chunks=queue.Queue(maxsize=64)
            def produce():
                try:
                    for delta in stream_answer(messages(self.history,text),cancel):
                        while not cancel.event.is_set():
                            try:chunks.put(('text',delta),timeout=.2);break
                            except queue.Full:continue
                except Exception as error:
                    while not cancel.event.is_set():
                        try:chunks.put(('error',error),timeout=.2);break
                        except queue.Full:continue
                finally:
                    while not cancel.event.is_set():
                        try:chunks.put(('done',None),timeout=.2);break
                        except queue.Full:continue
            threading.Thread(target=produce,daemon=True).start()
            answer='';buffer='';speaker=load().get('speaker','Serena')
            while True:
                cancel.check()
                try:kind,data=chunks.get(timeout=.3)
                except queue.Empty:continue
                if kind=='error':raise data
                if kind=='text':
                    answer+=data;buffer+=data
                    if len(answer)>2000:raise ValueError('回答过长，请缩短问题后重试')
                    event('answer',text=answer)
                sentences,buffer=take_sentences(buffer,final=kind=='done')
                for sentence in sentences:
                    cancel.check();event('status',state='Synthesizing',message='正在准备回答')
                    audio=engines.call('tts',{'op':'tts','text':sentence,'speaker':speaker})
                    event('audio',pcm=base64.b64decode(audio['pcm']),text=sentence,sample_rate=16000)
                if kind=='done':break
            if not answer.strip():raise ValueError('云端没有返回回答，请重试')
            cancel.check()
            with self.lock:
                cancel.check()
                if self.current is not cancel:raise Cancelled()
                self.history=(self.history+[{'role':'user','content':text},{'role':'assistant','content':answer}])[-12:]
            event('done',text=answer)
        finally:
            with self.lock:
                if self.current is cancel:self.current=None
