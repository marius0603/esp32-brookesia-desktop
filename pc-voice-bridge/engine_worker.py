"""Persistent model worker; one JSON request per line, no credentials."""
from pathlib import Path
import argparse, base64, contextlib, io, json, os, subprocess, sys, tempfile, time

parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=['tts','asr'],required=True)
args=parser.parse_args()
ROOT=Path(os.environ['QWEN_SPEECH_ROOT'])
os.environ.update(HF_HOME=str(ROOT/'cache/huggingface'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
    HF_HUB_DISABLE_TELEMETRY='1',TORCH_HOME=str(ROOT/'cache/torch'),CUDA_CACHE_PATH=str(ROOT/'cache/cuda'),
    TEMP=str(ROOT/'temp'),TMP=str(ROOT/'temp'))
protocol=sys.stdout
with contextlib.redirect_stdout(sys.stderr):
    import numpy as np
    import soundfile as sf
    import torch
    torch.set_num_threads(6)
    if not torch.cuda.is_available():raise RuntimeError('NVIDIA GPU unavailable')
model=None;processor=None

def load():
    global model,processor
    if model is not None:return
    if args.kind=='tts':
        from qwen_tts import Qwen3TTSModel
        model=Qwen3TTSModel.from_pretrained(str(ROOT/'models/Qwen3-TTS-12Hz-1.7B-CustomVoice'),
            device_map='cuda:0',dtype=torch.bfloat16,attn_implementation='sdpa',local_files_only=True)
    else:
        from transformers import AutoModelForMultimodalLM,AutoProcessor
        folder=str(ROOT/'models/Qwen3-ASR-1.7B-hf')
        processor=AutoProcessor.from_pretrained(folder,local_files_only=True)
        model=AutoModelForMultimodalLM.from_pretrained(folder,device_map='cuda:0',dtype=torch.bfloat16,
            attn_implementation='sdpa',local_files_only=True)

def handle(request):
    start=time.monotonic();load()
    if request['op']=='load':return {'ready':True,'gpu':torch.cuda.get_device_name(0)}
    if args.kind=='tts':
        from scipy.signal import resample_poly
        waves,rate=model.generate_custom_voice(text=request['text'],language=request.get('language','Chinese'),
            speaker=request.get('speaker','Serena'),instruct=request.get('instruct','温柔、清晰地朗读。'),max_new_tokens=1024)
        wave=np.asarray(waves[0],dtype=np.float32)
        if rate!=16000:wave=resample_poly(wave,16000,rate)
        wave=np.concatenate([wave,np.zeros(1600,dtype=np.float32)])
        pcm=(np.clip(wave,-1,1)*32767).astype('<i2').tobytes()
        if request.get('output'):sf.write(request['output'],np.frombuffer(pcm,dtype='<i2'),16000,subtype='PCM_16')
        return {'pcm':base64.b64encode(pcm).decode(),'sample_rate':16000,'audio_seconds':len(pcm)/32000,'elapsed_seconds':time.monotonic()-start}
    temporary=None
    if 'pcm' in request:
        raw=base64.b64decode(request['pcm'],validate=True)
        if len(raw)>960000 or len(raw)%2:raise ValueError('Invalid recording length')
        pieces=[np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768]
    else:
        import imageio_ffmpeg
        temporary=Path(tempfile.mktemp(suffix='.wav',prefix='voice-',dir=ROOT/'temp'))
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-nostdin','-v','error','-y','-i',request['input'],
            '-ar','16000','-ac','1',str(temporary)],check=True)
        def chunks():
            with sf.SoundFile(temporary) as audio:
                while True:
                    piece=audio.read(30*16000,dtype='float32')
                    if not len(piece):break
                    yield piece
        pieces=chunks()
    texts=[];language='';seconds=0
    try:
        for piece in pieces:
            if not len(piece):continue
            seconds+=len(piece)/16000
            inputs=processor.apply_transcription_request(audio=piece,language=request.get('language'),
                processor_kwargs={'audio_kwargs':{'sampling_rate':16000}}).to(model.device,model.dtype)
            with torch.inference_mode():output=model.generate(**inputs,max_new_tokens=1024,do_sample=False)
            parsed=processor.decode(output[:,inputs['input_ids'].shape[1]:],return_format='parsed')[0]
            texts.append(parsed['transcription']);language=parsed.get('language','')
    finally:
        if temporary:temporary.unlink(missing_ok=True)
    text='\n'.join(texts)
    if request.get('output'):Path(request['output']).write_text(text+'\n',encoding='utf-8')
    return {'text':text,'language':language,'audio_seconds':seconds,'elapsed_seconds':time.monotonic()-start}

for line in sys.stdin:
    try:
        request=json.loads(line)
        with contextlib.redirect_stdout(sys.stderr):result=handle(request)
        response={'id':request['id'],'ok':True,'result':result}
    except Exception as error:
        response={'id':request.get('id') if 'request' in locals() else None,'ok':False,'error':type(error).__name__+': '+str(error)[:300]}
    protocol.write(json.dumps(response,ensure_ascii=False)+'\n');protocol.flush()
