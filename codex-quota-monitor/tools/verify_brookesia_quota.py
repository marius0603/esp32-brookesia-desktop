"""Check the installed App, real quota file round trip, UI ACK and volume API."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quota_monitor.brookesia import StableUsbClient

packet = json.loads((ROOT / 'runtime/latest.json').read_text(encoding='utf-8'))
if packet.get('status') != 'ok' or time.time() - packet['sampled_at'] > 180:
    raise SystemExit('Read fresh quota with --once before verifying')
packet['bridge_at'] = int(time.time())
report = {}
with StableUsbClient('COM5', timeout=20) as client:
    report['hello'] = client.hello()
    apps = client.call('SystemCore', 'ListApps', {})['result']
    app = next(item for item in apps if item['manifest']['id'] == 'local.codex.quota')
    report['app_id'] = app['app_id']
    if app['state'] != 'Running':
        report['start'] = client.call('SystemCore', 'StartApp', {'AppId':app['app_id']})
    else:
        report['start'] = {'ok': True, 'already_running': True}
    report['write'] = client.call('Storage', 'FSWriteText', {
        'Path':'/littlefs/quota.json', 'Data':json.dumps(packet,ensure_ascii=False),
    })
    readback = json.loads(client.call('Storage','FSReadText',{'Path':'/littlefs/quota.json'})['result'])
    assert readback == packet, 'Device quota file differs from the host snapshot'
    report['quota_readback_matches'] = True
    report['sampled_at'] = packet['sampled_at']
    client.goodbye()
    client.serial.timeout = 0.5
    lines = bytearray()
    end = time.monotonic() + 10
    while time.monotonic() < end:
        lines.extend(client.serial.read(max(1,client.serial.in_waiting)))
    (ROOT/'runtime/brookesia-quota-ui.log').write_bytes(lines)
    report['ui_update_ack'] = f"Codex quota UI updated: {packet['sampled_at']}".encode() in lines
    client.serial.timeout = 20
    client.hello()
    report['active_app'] = client.call('SystemCore','GetActiveApp',{})['result']
    report['apps'] = client.call('SystemCore','ListApps',{})['result']
    volume = client.call('AudioPlayback','GetVolume',{})['result']
    try:
        target = max(0,volume-5)
        client.call('AudioPlayback','SetVolume',{'Volume':target})
        assert client.call('AudioPlayback','GetVolume',{})['result'] == target
        report['volume_api_roundtrip'] = True
    finally:
        client.call('AudioPlayback','SetVolume',{'Volume':volume})
    report['volume_restored'] = client.call('AudioPlayback','GetVolume',{})['result'] == volume
(ROOT/'runtime/brookesia-quota-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({key:report[key] for key in ('app_id','quota_readback_matches','ui_update_ack','volume_api_roundtrip','volume_restored')},indent=2))
if not report['ui_update_ack']:
    raise SystemExit('Quota reached storage but UI update ACK was not observed; inspect the runtime log')
