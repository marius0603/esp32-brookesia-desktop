"""Outbound public tunnel for cross-network validation; URL is intentionally temporary."""
from pathlib import Path
import ctypes,ctypes.wintypes as wt,json,os,re,subprocess,threading,time
from config_store import ROOT,load,save

state={'running':False,'url':'','error':''}

def matching_process(identifier,expected):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wt.DWORD,wt.BOOL,wt.DWORD];kernel.OpenProcess.restype=wt.HANDLE
    handle=kernel.OpenProcess(0x1000,False,identifier)
    if not handle:return False
    try:
        path=ctypes.create_unicode_buffer(32768);size=wt.DWORD(len(path))
        kernel.QueryFullProcessImageNameW.argtypes=[wt.HANDLE,wt.DWORD,wt.LPWSTR,ctypes.POINTER(wt.DWORD)]
        ok=kernel.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size))
        return bool(ok) and os.path.normcase(path.value)==os.path.normcase(str(expected))
    finally:
        kernel.CloseHandle.argtypes=[wt.HANDLE];kernel.CloseHandle(handle)

def run():
    config=load()
    if config.get('network_mode')!='quick_tunnel':return
    executable=ROOT/'tools/cloudflared.exe';pid_file=ROOT/'logs/tunnel.pid';log_path=ROOT/'logs/tunnel-current.log'
    if not executable.exists():state['error']='尚未安装公网隧道程序';return
    if pid_file.exists():
        try:
            if matching_process(int(pid_file.read_text()),executable):
                state.update(running=True,url=config.get('device_url',''));return
        except (ValueError,OSError):pass
    try:
        with log_path.open('w',encoding='utf-8') as log:
            process=subprocess.Popen([str(executable),'tunnel','--no-autoupdate','--protocol','http2','--edge-ip-version','4',
                '--url','http://127.0.0.1:'+str(config.get('gateway_port',7861))],cwd=ROOT,
                stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        pid_file.write_text(str(process.pid),encoding='ascii')
        for _ in range(120):
            if process.poll() is not None:raise RuntimeError('公网隧道启动失败，请查看 tunnel-current.log')
            if log_path.exists():
                text=log_path.read_text(encoding='utf-8',errors='replace')
                match=re.search(r'https://([a-z0-9-]+\.trycloudflare\.com)',text)
                if match:
                    address='wss://'+match.group(1)+'/device'
                    config=load();old=config.get('device_url');config['device_url']=address
                    config['device_address_changed']=bool(old and old!=address);save(config)
                    state.update(running=True,url=address);return
            time.sleep(.5)
        raise RuntimeError('公网隧道准备超时')
    except Exception as error:state['error']=str(error)[:180]

def start():threading.Thread(target=run,daemon=True).start()
