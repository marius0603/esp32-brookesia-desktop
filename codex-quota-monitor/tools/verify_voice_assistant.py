"""Verify app preservation, asynchronous connection and activation without recording."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quota_monitor.brookesia import StableUsbClient

parser = argparse.ArgumentParser()
parser.add_argument('--port', default='COM5')
parser.add_argument('--before', type=Path)
parser.add_argument('--output', type=Path, default=ROOT / 'runtime/assistant-verification.json')
args = parser.parse_args()
report = {}
with StableUsbClient(args.port, timeout=25) as client:
    client.hello()
    apps = client.call('SystemCore', 'ListApps', {})['result']
    installed = {a['manifest']['id']: a['manifest']['version'] for a in apps}
    if args.before:
        before = json.loads(args.before.read_text(encoding='utf-8'))
        assert all(installed.get(a['manifest']['id']) == a['manifest']['version'] for a in before)
        report['existing_apps_preserved'] = True
    app = next(a for a in apps if a['manifest']['id'] == 'local.voiceassistant')
    client.call('SystemCore', 'StartApp', {'AppId': app['app_id']})
    deadline = time.monotonic() + 65
    while time.monotonic() < deadline:
        active = client.call('SystemCore', 'GetActiveApp', {})['result']
        assert active['app_id'] == app['app_id'] and active['state'] == 'Running' and not active['last_error'], active
        state = client.call('VoiceAssistant', 'GetState', {})['result']
        if state['state'] in ('Activation', 'Ready', 'Error'):
            break
        time.sleep(.5)
    report.update(installed=installed, active=active, assistant=state)
    assert state['captured_frames'] == 0 and state['sent_packets'] == 0, state
    report['no_audio_captured_or_uploaded_on_open'] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'state':state['state'], 'message':state['message'], 'activation_code':state['activation_code'],
                      'existing_apps_preserved':report.get('existing_apps_preserved'), 'no_microphone_upload':True}, ensure_ascii=True), flush=True)
    assert state['state'] in ('Activation','Ready'), state
