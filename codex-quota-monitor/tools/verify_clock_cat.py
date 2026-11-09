"""Verify the approved sprite clock, real solar data and temporary day/night fixtures.

Never change system time, network credentials, parent policy or audio volume.
Fixtures are restored in finally; private recovery data stays under runtime/.
"""
import argparse
import datetime as dt
import json
import time
from pathlib import Path
from maintenance_client import SharedPowerDiagnosticClient

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'brookesia-apps/flip-clock/src'
RUNTIME = ROOT / 'codex-quota-monitor/runtime'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM5')
    args = parser.parse_args()
    report = {'passed': False, 'fixtures': []}
    with SharedPowerDiagnosticClient(args.port, timeout=30) as client:
        client.hello()
        def call(service, name, params=None):
            return client.call_timeout(service, name, params or {})['result']
        def read(path):
            return call('Storage', 'FSReadText', {'Path': path})
        def write(path, value):
            call('Storage', 'FSWriteText', {'Path': path, 'Data': json.dumps(value, ensure_ascii=False)})
        def memory():
            value = call('PhoneProvisioning', 'GetState')
            return {key: value[key] for key in ('internal_free_bytes', 'psram_free_bytes', 'largest_dma_block')}
        def state():
            return json.loads(read('/littlefs/clock-state.json'))
        def wait_cat(expected=None, solar=False):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                value = state()
                if (value.get('face') == 2 and value.get('cat_updates', 0) >= 8
                    and (expected is None or value['cat_scene'] == expected)
                    and (not solar or value['solar']['source'] == 'sunrise_sunset')):
                    assert not value['cat_error'], value
                    return value
                time.sleep(.25)
            raise AssertionError(value)
        for service in ('Audiobook', 'Radio', 'VoiceAssistant', 'LocalVoice'):
            assert not call(service, 'GetState')['active'], 'Finish active audio first'
        modes = call('DeviceModes', 'GetState')
        assert not modes['screen_locked'], 'Unlock first'
        call('DeviceModes', 'Wake')
        apps = call('SystemCore', 'ListApps')
        app = next(item for item in apps if item['manifest']['id'] == 'local.flipclock')
        assert app['manifest']['version'] == '0.2.1'
        original_apps = {item['manifest']['id']: item['manifest']['version'] for item in apps}
        for name in ('app/main.js', 'res/screens/main.json', 'res/images/index.json'):
            assert read('/sdcard/apps/local.flipclock/' + name).replace('\r\n', '\n') == (APP / name).read_text(encoding='utf-8'), name
        for phase in ('day', 'night'):
            for number in range(8):
                name = f'res/images/cat_{phase}_{number}.bin'
                info = call('Storage', 'FSStat', {'Path': '/sdcard/apps/local.flipclock/' + name})
                assert info['exists'] and info['size'] == (APP / name).stat().st_size, name
        paths = ('/littlefs/clock-weather.json', '/littlefs/clock-face.json')
        originals = {path: read(path) if call('Storage', 'FSStat', {'Path': path})['exists'] else None for path in paths}
        recovery = RUNTIME / 'clock-cat-fixture-recovery.json'
        recovery.write_text(json.dumps(originals, ensure_ascii=False, indent=2), encoding='utf-8')
        def reopen(face):
            call('SystemCore', 'StopApp', {'AppId': app['app_id']})
            write(paths[1], {'face': face})
            call('SystemCore', 'StartApp', {'AppId': app['app_id']})
            active = call('SystemCore', 'GetActiveApp')
            assert active['app_id'] == app['app_id'] and active['state'] == 'Running' and not active['last_error'], active
        try:
            reopen(2)
            real = wait_cat(solar=True)
            report['real_solar'] = real
            samples = [memory()]
            for _ in range(5):
                time.sleep(2)
                samples.append(memory())
            report['memory_samples'] = samples
            assert min(sample['psram_free_bytes'] for sample in samples) > 500000, samples
            base = json.loads(read(paths[0]))
            today = dt.datetime.fromtimestamp(real['time']/1000, dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%d')
            minute = dt.datetime.fromtimestamp(real['time']/1000, dt.timezone(dt.timedelta(hours=8))).strftime('%H:%M')
            for expected in ('night', 'day'):
                # Deliberately contradict is_day so the test requires solar priority.
                fixture = json.loads(json.dumps(base))
                weather = fixture['weather']
                weather['day'] = 1 if expected == 'night' else 0
                weather['received_at'] = int(time.time()*1000) + 60000
                rise, end = ('00:00', '23:59') if expected == 'day' else ('00:00', '00:01')
                if expected == 'night' and minute == '00:00':
                    rise, end = '12:00', '12:01'
                weather['solar'] = {'utc_offset_seconds': 28800, 'daily': {'time': [today],
                                    'sunrise': [today+'T'+rise], 'sunset': [today+'T'+end]}}
                call('SystemCore', 'StopApp', {'AppId': app['app_id']})
                write(paths[0], fixture)
                reopen(2)
                result = wait_cat(expected, solar=True)
                report['fixtures'].append({'phase': expected, 'updates': result['cat_updates'],
                                           'max_set_source_ms': result['cat_max_ms'], 'error': result['cat_error']})
            for face in (0, 1, 2):
                reopen(face)
                value = state()
                assert value['face'] == face
            report['faces_reopened'] = [0, 1, 2]
        finally:
            call('SystemCore', 'StopApp', {'AppId': app['app_id']})
            for path, original in originals.items():
                if original is None:
                    if call('Storage', 'FSStat', {'Path': path})['exists']:
                        call('Storage', 'FSRemove', {'Path': path})
                else:
                    call('Storage', 'FSWriteText', {'Path': path, 'Data': original})
            call('DeviceModes', 'Wake')
            call('SystemCore', 'StartApp', {'AppId': app['app_id']})
            recovery.unlink()
        report['restored_real_solar'] = wait_cat(solar=True)
        assert {item['manifest']['id']: item['manifest']['version'] for item in call('SystemCore','ListApps')} == original_apps
        assert call('DeviceModes', 'GetState')['resume_volume'] == modes['resume_volume']
        report.update(passed=True, apps_preserved=len(apps), volume_preserved=modes['resume_volume'], final_memory=memory())
    (RUNTIME / 'clock-cat-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
