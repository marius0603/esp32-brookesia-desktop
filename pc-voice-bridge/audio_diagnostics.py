"""One explicitly armed recording, retained locally for microphone diagnosis."""
from array import array
import datetime,json,math,sys,uuid,wave
from config_store import ROOT,load,save

def capture_if_armed(pcm):
    config=load()
    if not config.get('diagnostic_next_recording'):return None
    config['diagnostic_next_recording']=False;save(config)
    if not pcm or len(pcm)%2:raise ValueError('Invalid diagnostic PCM')
    samples=array('h');samples.frombytes(pcm)
    if sys.byteorder!='little':samples.byteswap()
    count=len(samples);peak=max(abs(x) for x in samples)
    rms=math.sqrt(sum(x*x for x in samples)/count)
    result={'seconds':count/16000,'peak':peak,'rms_dbfs':round(20*math.log10(max(rms,1)/32768),2),
        'dc_offset':round(sum(samples)/count,2),'clipped_fraction':sum(abs(x)>=32760 for x in samples)/count,
        'zero_fraction':samples.count(0)/count}
    folder=ROOT/'outputs/diagnostics';folder.mkdir(parents=True,exist_ok=True)
    name=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    target=folder/(name+'.wav')
    with wave.open(str(target),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000);output.writeframes(pcm)
    result['file']=str(target)
    target.with_suffix('.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
