"""Outbound public tunnel for cross-network validation; URL is intentionally temporary."""
from pathlib import Path
import ctypes,ctypes.wintypes as wt,json,os,re,subprocess,threading,time
from config_store import ROOT,load,save

state={'running':False,'url':'','error':''}

def ssh_executable():return Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/OpenSSH/ssh.exe'

def ssh_endpoint(log):
    matches=re.findall(r'https://([a-z0-9-]+\.(?:lhr\.life|localhost\.run))',log)
    return 'wss://'+matches[-1]+'/device' if matches else ''

def owned_ssh_process(identifier):
    if not matching_process(identifier,ssh_executable()):return False
    query=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
        f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(identifier)}').CommandLine"],
        capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
    command=os.path.normcase(query.stdout)
    return 'nokey@localhost.run' in command and os.path.normcase(str(ROOT/'config/ssh-tunnel-known-hosts')) in command

def run_ssh(config):
    executable=ssh_executable();pid_file=ROOT/'logs/ssh-tunnel.pid';log_path=ROOT/'logs/ssh-tunnel.log'
    try:
        if pid_file.exists() and owned_ssh_process(int(pid_file.read_text())):
            state.update(running=True,url=config.get('device_url',''),error='',provider='localhost.run');return
        arguments=[str(executable),'-T','-o','BatchMode=yes','-o','ConnectTimeout=20',
            '-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3','-o','ExitOnForwardFailure=yes',
            '-o','IdentityAgent=none','-o','IdentitiesOnly=yes','-o','IdentityFile=none',
            '-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(ROOT/'config/ssh-tunnel-known-hosts'),
            '-R','80:127.0.0.1:'+str(config.get('gateway_port',7861)),'nokey@localhost.run']
        with log_path.open('w',encoding='utf-8') as log:
            process=subprocess.Popen(arguments,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,
                stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        pid_file.write_text(str(process.pid),encoding='ascii')
        for _ in range(120):
            if process.poll() is not None:raise RuntimeError('备用公网入口启动失败，请查看 ssh-tunnel.log')
            address=ssh_endpoint(log_path.read_text(encoding='utf-8',errors='replace'))
            if address:
                config=load();old=config.get('device_url');config['device_url']=address
                config['device_address_changed']=bool(old and old!=address);save(config)
                state.update(running=True,url=address,error='',provider='localhost.run');return
            time.sleep(.5)
        raise RuntimeError('备用公网入口准备超时')
    except Exception as error:state.update(running=False,error=str(error)[:180])

def snapshot():
    """A live process alone does not prove the temporary public route still exists."""
    result=dict(state)
    config=load()
    if config.get('network_mode')=='ssh_tunnel':
        result.update(url=config.get('device_url',''),provider='localhost.run')
        try:running=matching_process(int((ROOT/'logs/ssh-tunnel.pid').read_text()),ssh_executable())
        except (ValueError,OSError):running=False
        result.update(running=running,error='' if running else '公网中转已停止，请重新启动工作台')
        return result
    if config.get('network_mode')!='quick_tunnel':return result
    result['url']=config.get('device_url',result['url'])
    log_path=ROOT/'logs/tunnel-current.log'
    try:
        lines=log_path.read_text(encoding='utf-8',errors='replace').splitlines()
        registered=max((i for i,line in enumerate(lines) if 'Registered tunnel connection' in line),default=-1)
        expired=max((i for i,line in enumerate(lines) if 'Unauthorized: Tunnel not found' in line),default=-1)
        if expired>registered:
            result.update(running=False,error='临时公网入口已失效，请重建隧道后通过 USB 重新配对')
    except OSError:pass
    return result

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
    if config.get('network_mode')=='ssh_tunnel':return run_ssh(config)
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
