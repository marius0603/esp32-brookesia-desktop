"""Private per-user configuration; API credentials use Windows DPAPI."""
from pathlib import Path
import base64, ctypes, ctypes.wintypes as wt, json, os, secrets, sys

ROOT=Path(os.environ.get('QWEN_SPEECH_ROOT',Path(__file__).resolve().parents[1]))
CONFIG=ROOT/'config/assistant.json'

class Blob(ctypes.Structure):
    _fields_=[('length',wt.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]

def protect(data,decrypt=False):
    raw=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(raw,ctypes.POINTER(ctypes.c_ubyte)))
    output=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    func=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    func.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wt.DWORD,ctypes.POINTER(Blob)]
    func.restype=wt.BOOL
    if not func(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:return ctypes.string_at(output.data,output.length)
    finally:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.LocalFree.argtypes=[ctypes.c_void_p]
        kernel.LocalFree(ctypes.cast(output.data,ctypes.c_void_p))

def load():
    if CONFIG.exists():return json.loads(CONFIG.read_text(encoding='utf-8'))
    return {'base_url':'https://api.deepseek.com/v1','model':'deepseek-flash','speaker':'Serena',
        'device_token':secrets.token_hex(24),'device_ip':'','gateway_port':7861}

def save(config):
    CONFIG.parent.mkdir(parents=True,exist_ok=True)
    temporary=CONFIG.with_suffix('.tmp')
    temporary.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(CONFIG)

def set_key(value):
    config=load()
    config['api_key_dpapi']=base64.b64encode(protect(value.strip().encode())).decode('ascii')
    save(config)

def api_key(config=None):
    config=config or load()
    if not config.get('api_key_dpapi'):raise ValueError('请先在电脑端配置云服务密钥')
    return protect(base64.b64decode(config['api_key_dpapi']),decrypt=True).decode()

def public(config=None):
    config=config or load()
    return {k:config.get(k) for k in ('base_url','model','speaker','device_ip','gateway_port','network_mode','device_url','device_address_changed')} | {'key_configured':bool(config.get('api_key_dpapi'))}

if __name__=='__main__':
    if '--set-key' in sys.argv:
        set_key(sys.stdin.read());print('Credential stored using Windows user encryption.')
    else:print(json.dumps(public(),ensure_ascii=False))
