"""Check preserved apps and quota delivery, recording real render timings."""
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quota_monitor.brookesia import StableUsbClient

packet = json.loads((ROOT / 'runtime/latest.json').read_text(encoding='utf-8'))
if packet.get('status') != 'ok' or time.time() - packet['sampled_at'] > 180:
    raise SystemExit('Read fresh quota with --once before verifying')
packet['bridge_at'] = int(time.time())
report = {'build': '0.8.3-s3.2', 'apps': [], 'physical_touch_verified': False}
console = bytearray()
with StableUsbClient('COM5', timeout=30) as client:
    client.hello()
    outputs = client.call('Display', 'GetOutputs', {})['result']
    report['outputs'] = outputs
    assert outputs[0]['touch']['max_points'] == 1, 'Unexpected touch capability'
    apps = client.call('SystemCore', 'ListApps', {})['result']
    for manifest_id in ('brookesia.general.files', 'brookesia.general.settings', 'local.codex.quota'):
        app = next(item for item in apps if item['manifest']['id'] == manifest_id)
        started = time.monotonic()
        client.call('SystemCore', 'StartApp', {'AppId': app['app_id']})
        elapsed = time.monotonic() - started
        active = client.call('SystemCore', 'GetActiveApp', {})['result']
        assert active['app_id'] == app['app_id'] and active['state'] == 'Running', active
        assert not active['last_error'], active
        report['apps'].append({'manifest_id': manifest_id, 'start_call_seconds': round(elapsed, 3),
                               'state': active['state'], 'last_error': active['last_error']})
        if manifest_id == 'local.codex.quota':
            client.call('Storage', 'FSWriteText', {'Path': '/littlefs/quota.json',
                        'Data': json.dumps(packet, ensure_ascii=False)})
            readback = json.loads(client.call('Storage', 'FSReadText', {'Path': '/littlefs/quota.json'})['result'])
            assert readback == packet
            report['quota_readback_matches'] = True
        client.goodbye()
        client.serial.timeout = 0.5
        end = time.monotonic() + 7
        while time.monotonic() < end:
            console.extend(client.serial.read(max(1, client.serial.in_waiting)))
        client.serial.timeout = 30
        client.hello()
        client.call('SystemCore', 'RequestCloseApp', {'AppId': app['app_id']})
    deadline = time.monotonic() + 5
    while True:
        report['final_active_app'] = client.call('SystemCore', 'GetActiveApp', {})['result']
        if report['final_active_app']['manifest']['id'] != 'local.codex.quota' or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    assert report['final_active_app']['manifest']['id'] != 'local.codex.quota', 'Failed to return to desktop'
report['quota_ui_ack'] = f"Codex quota UI updated: {packet['sampled_at']}".encode() in console
report['render_samples'] = [dict(zip(('cycles', 'avg_us', 'max_us'), map(int, values)))
                            for values in re.findall(rb'render cycles=(\d+) avg_us=(\d+) max_us=(\d+)', console)]
(ROOT / 'runtime/brookesia-s3.2-ui.log').write_bytes(console)
(ROOT / 'runtime/brookesia-s3.2-ui-verification.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: report[key] for key in ('apps', 'quota_readback_matches', 'quota_ui_ack', 'render_samples')}, indent=2))
assert report['quota_ui_ack'], 'Quota file reached device but UI ACK was not observed'
