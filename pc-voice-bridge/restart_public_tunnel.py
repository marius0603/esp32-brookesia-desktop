"""Explicitly recreate a temporary public route; USB pairing is required afterward."""
import argparse,os,subprocess,sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',type=Path,required=True)
    args=parser.parse_args();root=args.target.resolve()
    os.environ['QWEN_SPEECH_ROOT']=str(root)
    sys.path.insert(0,str(root/'scripts'))
    import config_store,public_tunnel
    if config_store.load().get('network_mode')!='quick_tunnel':
        raise SystemExit('Only temporary quick tunnels can be recreated with this tool')
    pid_file=root/'logs/tunnel.pid'
    if pid_file.exists():
        identifier=int(pid_file.read_text())
        if public_tunnel.matching_process(identifier,root/'tools/cloudflared.exe'):
            subprocess.run(['taskkill','/PID',str(identifier),'/F'],check=True,capture_output=True)
    public_tunnel.run()
    result=public_tunnel.snapshot()
    if not result['running']:raise SystemExit(result['error'] or 'Tunnel is not ready')
    print('New temporary endpoint prepared. Pair the device over USB before use.')

if __name__=='__main__':main()
