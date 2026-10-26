"""OpenAI-compatible streaming client; credentials never enter model workers."""
import json,threading,time,urllib.error,urllib.request
from config_store import load,api_key

class Cancelled(Exception):pass

class Cancellation:
    def __init__(self):self.event=threading.Event();self.response=None
    def cancel(self):
        self.event.set()
        try:
            import socket
            self.response.fp.raw._sock.shutdown(socket.SHUT_RDWR)
        except (AttributeError,OSError):pass
    def check(self):
        if self.event.is_set():raise Cancelled()

def stream_answer(messages,cancel):
    config=load();key=api_key(config)
    body={'model':config['model'],'messages':messages,'stream':True,'max_tokens':450,
        'thinking':{'type':'disabled'}}
    request=urllib.request.Request(config['base_url'].rstrip('/')+'/chat/completions',
        data=json.dumps(body,ensure_ascii=False).encode('utf-8'),
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'text/event-stream'})
    started=time.monotonic();finished=False
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            cancel.response=response
            for raw in response:
                cancel.check()
                if time.monotonic()-started>120:raise TimeoutError('云端回答超时，请重试')
                line=raw.decode('utf-8').strip()
                if not line.startswith('data:'):continue
                value=line[5:].strip()
                if value=='[DONE]':finished=True;break
                data=json.loads(value)
                if data.get('error'):raise RuntimeError('云服务返回错误')
                for choice in data.get('choices',[]):
                    text=choice.get('delta',{}).get('content')
                    if isinstance(text,str) and text:yield text
                    if choice.get('finish_reason') in ('stop','length'):finished=True
            cancel.check()
            if not finished:raise RuntimeError('云端回答中断，请重试')
    except urllib.error.HTTPError as error:
        raise RuntimeError('云服务请求失败，HTTP '+str(error.code)) from None
    finally:cancel.response=None

SYSTEM='你是家庭语音助手。默认用自然、简洁的中文回答，通常不超过三句话。第一句尽量简短，适合直接朗读。不要使用Markdown、表格或链接。用户明确要求讲故事时可以适当展开。'

def messages(history,text):
    bounded=[];count=0
    for item in reversed(history[-12:]):
        if count+len(item['content'])>6000:break
        bounded.append(item);count+=len(item['content'])
    return [{'role':'system','content':SYSTEM}]+list(reversed(bounded))+[{'role':'user','content':text[:1200]}]

def take_sentences(buffer,final=False):
    import re
    chunks=[]
    while buffer:
        end=next((i+1 for i,c in enumerate(buffer[:48]) if c in '。！？!?\n' and i>=5),None)
        if end is None and len(buffer)>=48:
            candidates=[i+1 for i,c in enumerate(buffer[:48]) if c in '，,；;、 ' and i>=12]
            end=candidates[-1] if candidates else 48
        if end is None:
            if final:chunks.append(buffer.strip());buffer=''
            break
        piece=buffer[:end].strip();buffer=buffer[end:]
        if piece:chunks.append(piece)
    return chunks,buffer
