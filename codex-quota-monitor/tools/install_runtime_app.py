"""Install a BPK; reconnect after the known asynchronous directory-cleanup timeout."""
import argparse
import json
from pathlib import Path
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from quota_monitor.brookesia import StableUsbClient

parser=argparse.ArgumentParser()
parser.add_argument('bpk',type=Path)
parser.add_argument('--port',default='COM5')
args=parser.parse_args()
with zipfile.ZipFile(args.bpk) as archive:
    assert archive.testzip() is None
    manifest=json.loads(archive.read('manifest.json'))
app_id=manifest['package']['id']
for attempt in range(3):
    try:
        with StableUsbClient(args.port,timeout=15) as client:
            client.hello()
            apps=client.call('SystemCore','ListApps',{})['result']
            old=next((a for a in apps if a['manifest']['id']==app_id),None)
            if old and old['state']=='Running':
                client.call('SystemCore','StopApp',{'AppId':old['app_id']})
            result=client.transfer('install_bpk',args.bpk,None,False)
            print(json.dumps(result,indent=2),flush=True)
        break
    except RuntimeError as exc:
        if attempt==2 or 'Wait timeout after 5000 ms' not in str(exc):
            raise
        print('Waiting for directory cleanup; next attempt uses a fresh USB hello session.',flush=True)
        time.sleep(7)
