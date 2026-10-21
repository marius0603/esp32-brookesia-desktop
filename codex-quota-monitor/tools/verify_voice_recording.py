"""Regression with REAL microphone upload; requires explicit --record.

Run only for an authorized device recording check. No recognized text is logged.
"""
import argparse
import json
from pathlib import Path
import time
from verify_child_mode import Client

ROOT = Path(__file__).resolve().parents[1]


class CaptureClient(Client):
    def read_json(self):
        try:
            return super().read_json()
        except Exception as exc:
            data = str(exc).encode() + b'\n'
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                data += self.serial.read(max(1, self.serial.in_waiting))
            (ROOT/'runtime/voice-recording-crash-private.log').write_bytes(data)
            raise RuntimeError('Voice check interrupted; private diagnostic retained') from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', action='store_true')
    parser.add_argument('--port', default='COM5')
    args = parser.parse_args()
    if not args.record:
        parser.error('This test uploads microphone audio; explicitly pass --record')
    report = {'turns': []}
    with CaptureClient(args.port, timeout=25) as client:
        client.hello()

        def call(service, function, params=None):
            return client.call(service, function, params or {})['result']

        apps = call('SystemCore', 'ListApps')
        ids = {app['manifest']['id']: app['app_id'] for app in apps}

        def close_current():
            active = call('SystemCore', 'GetActiveApp')
            if active.get('manifest', {}).get('id') not in (None, 'brookesia.system.super.shell'):
                client.call('SystemCore', 'RequestCloseApp', {'AppId': active['app_id']})
                time.sleep(.7)

        close_current()
        # Warm the heavier weather UI before exercising audio allocation.
        call('SystemCore', 'StartApp', {'AppId': ids['local.weather']})
        time.sleep(1)
        close_current()
        call('SystemCore', 'StartApp', {'AppId': ids['local.voiceassistant']})
        deadline = time.monotonic() + 65
        while time.monotonic() < deadline:
            state = call('VoiceAssistant', 'GetState')
            if state['state'] in ('Ready', 'Error', 'Activation'):
                break
            time.sleep(.25)
        assert state['state'] == 'Ready', state['state']
        print('Voice ready', flush=True)
        try:
            for turn in range(3):
                before = state['sent_packets']
                call('VoiceAssistant', 'StartListening')
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    time.sleep(.15)
                    state = call('VoiceAssistant', 'GetState')
                    assert state['active'] and state['state'] != 'Error', state['state']
                assert state['sent_packets'] > before, 'No audio uploaded'
                if state['state'] == 'Listening':
                    call('VoiceAssistant', 'StopListening')
                time.sleep(1)
                state = call('VoiceAssistant', 'GetState')
                assert state['active'] and state['state'] != 'Error', state['state']
                keys = ('state', 'captured_frames', 'sent_packets', 'received_packets', 'played_bytes',
                        'stack_peak_used_bytes', 'control_stack_free_min_bytes',
                        'internal_free_bytes', 'internal_largest_bytes')
                report['turns'].append({key: state[key] for key in keys})
                print('Recording turn', turn + 1, 'passed', flush=True)
                call('VoiceAssistant', 'Interrupt')
                time.sleep(.4)
                state = call('VoiceAssistant', 'GetState')
        finally:
            call('VoiceAssistant', 'Disconnect')
        for _ in range(60):
            if not call('VoiceAssistant', 'GetState')['active']:
                break
            time.sleep(.2)
        close_current()
        report['resources'] = call('SdResources', 'GetState')
        report['child'] = call('ChildMode', 'GetState')
    (ROOT/'runtime/voice-recording-regression.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['turns']), flush=True)


if __name__ == '__main__':
    main()
