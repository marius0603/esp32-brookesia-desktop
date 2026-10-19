"""Verify the installed weather app; optionally exercise actual Wi-Fi reconnect."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quota_monitor.brookesia import StableUsbClient

parser = argparse.ArgumentParser()
parser.add_argument('--network-test', action='store_true')
args = parser.parse_args()
report = {}
with StableUsbClient('COM5', timeout=30) as client:
    client.hello()
    def state():
        return json.loads(client.call('Storage', 'FSReadText', {'Path':'/littlefs/weather-state.json'})['result'])
    def wait_for(predicate, timeout=90):
        end = time.monotonic()+timeout
        while time.monotonic()<end:
            try:
                value = state()
                if predicate(value):
                    return value
            except (RuntimeError, ValueError):
                pass
            time.sleep(0.5)
        raise RuntimeError('Weather state timed out')
    apps = client.call('SystemCore', 'ListApps', {})['result']
    app = next(item for item in apps if item['manifest']['id']=='local.weather')
    assert app['manifest']['version']=='0.2.2'
    report['app_id'] = app['app_id']
    client.call('SystemCore', 'StartApp', {'AppId':app['app_id']})
    report['initial'] = wait_for(lambda value: value.get('version')==2 and value.get('received_at') and
        value.get('hourly_count')==24 and value.get('ui_updated') and not value.get('pending') and
        (value.get('background') not in ('rain','storm') or value.get('fx_frames',0)>=8))
    assert not report['initial']['fx_error']
    print(json.dumps(report['initial'],ensure_ascii=False),flush=True)
    if args.network_test:
        assert client.call('Wifi','GetGeneralState',{})['result']=='Connected'
        try:
            client.call('Wifi','TriggerGeneralAction',{'Action':'Disconnect'})
            report['offline'] = wait_for(lambda value: not value.get('connected'),15)
            assert report['offline']['received_at']==report['initial']['received_at']
            assert report['offline']['temperature']==report['initial']['temperature']
            print('Offline cache confirmed',flush=True)
        finally:
            if client.call('Wifi','GetGeneralState',{})['result']!='Connected':
                client.call('Wifi','TriggerGeneralAction',{'Action':'Connect'})
        report['reconnected'] = wait_for(lambda value: value.get('connected') and not value.get('pending') and
            value.get('received_at',0)>report['initial']['received_at'] and not value.get('error'),45)
        print('Wi-Fi reconnect automatically fetched fresh weather',flush=True)
    report['cache'] = json.loads(client.call('Storage','FSReadText',{'Path':'/littlefs/weather-cache.json'})['result'])
    assert len(report['cache']['data']['hourly']['time'])>=24
    report['active_app'] = client.call('SystemCore','GetActiveApp',{})['result']
    assert report['active_app']['app_id']==app['app_id'] and report['active_app']['state']=='Running'
    assert not report['active_app']['last_error']
    report['storage_capacity'] = client.call('Storage','GetFileSystemCapacity',{'MountPoint':'/littlefs'})['result']
(ROOT/'runtime/weather-verification-0.2.2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Weather verification passed')
