"""Offline GPU inference in the model's own Python environment."""
from pathlib import Path
import argparse, json, os, re, subprocess, time

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(HF_HOME=str(ROOT/'cache/huggingface'), HF_HUB_OFFLINE='1',
    TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
    TORCH_HOME=str(ROOT/'cache/torch'), CUDA_CACHE_PATH=str(ROOT/'cache/cuda'),
    TORCHINDUCTOR_CACHE_DIR=str(ROOT/'cache/torchinductor'),
    TEMP=str(ROOT/'temp'), TMP=str(ROOT/'temp'), PYTHONUTF8='1')

def sections(text, limit=180):
    result=[]; current=''
    for sentence in re.findall(r'[^。！？；\n]+[。！？；]?|[。！？；]', text):
        if current and len(current)+len(sentence)>limit:
            result.append(current);current=''
        while len(sentence)>limit:
            if current: result.append(current);current=''
            result.append(sentence[:limit]);sentence=sentence[limit:]
        current+=sentence
    if current.strip():result.append(current)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('task',choices=['tts','asr']);p.add_argument('--request',type=Path,required=True)
    args=p.parse_args();request=json.loads(args.request.read_text(encoding='utf-8'))
    import numpy as np
    import soundfile as sf
    import torch
    if not torch.cuda.is_available():raise RuntimeError('NVIDIA GPU is not available')
    torch.set_num_threads(8)
    torch.manual_seed(42)
    started=time.monotonic()
    result={'task':args.task,'device':torch.cuda.get_device_name(0),'dtype':'bfloat16'}
    if args.task=='tts':
        from qwen_tts import Qwen3TTSModel
        model=Qwen3TTSModel.from_pretrained(str(ROOT/'models/Qwen3-TTS-12Hz-1.7B-CustomVoice'),
            device_map='cuda:0',dtype=torch.bfloat16,attn_implementation='sdpa',local_files_only=True)
        result['load_seconds']=time.monotonic()-started
        chunks=[]
        for text in sections(request['text']):
            waves, rate=model.generate_custom_voice(text=text,language='Chinese',
                speaker=request.get('speaker','Vivian'),instruct=request.get('instruct','温柔、清晰地朗读。'),
                max_new_tokens=2048)
            chunks.extend([np.asarray(waves[0],dtype=np.float32),np.zeros(int(rate*.18),dtype=np.float32)])
        if not chunks:raise ValueError('Please enter text')
        wave=np.concatenate(chunks)
        target=Path(request['output']);target.parent.mkdir(parents=True,exist_ok=True)
        sf.write(target,wave,rate,subtype='PCM_16')
        result.update(output=str(target),sample_rate=rate,audio_seconds=len(wave)/rate,
            speakers=model.get_supported_speakers(),languages=model.get_supported_languages())
    else:
        import imageio_ffmpeg
        from transformers import AutoModelForMultimodalLM, AutoProcessor
        converted=args.request.with_name(args.request.stem+'-16k.wav')
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-nostdin','-v','error','-y','-i',request['input'],
            '-ar','16000','-ac','1',str(converted)],check=True)
        audio,rate=sf.read(converted,dtype='float32')
        folder=str(ROOT/'models/Qwen3-ASR-1.7B-hf')
        processor=AutoProcessor.from_pretrained(folder,local_files_only=True)
        model=AutoModelForMultimodalLM.from_pretrained(folder,device_map='cuda:0',
            dtype=torch.bfloat16,attn_implementation='sdpa',local_files_only=True)
        result['load_seconds']=time.monotonic()-started
        texts=[]
        for at in range(0,len(audio),30*rate):
            piece=audio[at:at+30*rate]
            inputs=processor.apply_transcription_request(audio=piece,language=request.get('language','Chinese'),
                processor_kwargs={'audio_kwargs':{'sampling_rate':rate}}).to(model.device,model.dtype)
            with torch.inference_mode():
                output=model.generate(**inputs,max_new_tokens=1024,do_sample=False)
            generated=output[:,inputs['input_ids'].shape[1]:]
            texts.append(processor.decode(generated,return_format='transcription_only')[0])
        result.update(text='\n'.join(texts),audio_seconds=len(audio)/rate)
        if request.get('output'):
            Path(request['output']).write_text(result['text']+'\n',encoding='utf-8')
    result.update(elapsed_seconds=time.monotonic()-started,
        peak_gpu_gib=torch.cuda.max_memory_allocated()/1024**3)
    args.request.with_suffix('.result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
