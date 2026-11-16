"""Bounded real-device soak: media, real sleep timer, UI churn and BLE resources.

Private settings and samples stay in runtime. No firmware or app code is deployed;
player preferences are saved before testing and restored afterward.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
from maintenance_client import SharedPowerDiagnosticClient

ROOT = Path(__file__).resolve().parents[2]
TZ = timezone(timedelta(hours=8))


def replace_status(temp, target):
    # Windows readers/antivirus can briefly deny FILE_SHARE_DELETE. Preserve
    # the previous complete JSON and retry the rename, never truncate it.
    for attempt in range(61):
        try:
            temp.replace(target)
            return
        except PermissionError:
            if attempt == 60:
                raise
            time.sleep(.05)


class HostAwake:
    """Keep Windows awake for this process; leave display sleep and policy alone."""
    def __enter__(self):
        if sys.platform == 'win32':
            import ctypes
            self.kernel = ctypes.windll.kernel32
            if not self.kernel.SetThreadExecutionState(0x80000001):
                raise RuntimeError('Cannot keep host awake for the test')
        return self

    def __exit__(self, *_):
        if sys.platform == 'win32':
            self.kernel.SetThreadExecutionState(0x80000000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--minutes', type=int, default=120)
    parser.add_argument('--workload', choices=['full', 'apps'], default='full',
                        help='apps runs only UI/BLE switching, without replaying the media phases')
    args = parser.parse_args()
    if not 4 <= args.minutes <= 1440:
        parser.error('minutes must be 4..1440')
    stamp = datetime.now(TZ).strftime('%Y%m%d-%H%M%S')
    folder = ROOT / 'codex-quota-monitor/runtime' / ('audio-soak-' + stamp)
    folder.mkdir(parents=True)
    stop_file = ROOT / 'codex-quota-monitor/runtime/audio-soak-stop.request'
    if stop_file.exists():
        raise RuntimeError('Existing stop request must be reviewed before starting')
    report = {'status': 'preflight', 'passed': False, 'minutes': args.minutes, 'workload': args.workload,
              'started_at': None, 'phases': [], 'issues': [], 'samples': 0,
              'pcm_output_test_is_muted': True, 'offline_recognition_tested': False,
              'radio_stream_tested': False}

    def save():
        temp = folder / 'status.tmp'
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        replace_status(temp, folder / 'status.json')

    def issue(kind, **data):
        value = dict(kind=kind, **data)
        if value not in report['issues']:
            report['issues'].append(value)
            print(json.dumps({'event': 'issue', **value}, ensure_ascii=False), flush=True)

    save()
    with HostAwake(), SharedPowerDiagnosticClient(args.port, timeout=35) as client:
        client.hello()
        def f(service, name, params=None):
            return client.call_timeout(service, name, params or {})['result']
        def state():
            return f('Audiobook', 'GetState')
        before = f('DeviceModes', 'GetState')
        child = f('ChildMode', 'GetState')
        assert not child['enabled'], 'Parent policy must not be bypassed'
        assert not before['screen_locked'], 'Unlock the device before testing'
        for service in ['Audiobook', 'Radio', 'VoiceAssistant', 'LocalVoice', 'LearningAudio']:
            value = f(service, 'GetState')
            assert not value['active'], 'Active audio must finish before testing'
        original_book = state()
        assert not original_book['sleep_active'], 'An existing sleep timer must finish first'
        apps = f('SystemCore', 'ListApps')
        ids = {a['manifest']['id']: a['app_id'] for a in apps}
        versions = {a['manifest']['id']: a['manifest']['version'] for a in apps}
        current = f('SystemCore', 'GetActiveApp')
        stories = f('Audiobook', 'List')['tracks']
        songs = f('Audiobook', 'ListSongs')['tracks']
        nursery = [t for t in songs if '/lullabies/' not in t['path']]
        lullabies = [t for t in songs if '/lullabies/' in t['path']]
        assert len(stories) == 30 and len(nursery) == 20 and len(lullabies) == 10
        ble_before = f('PhoneProvisioning', 'GetState')
        saved = {}
        for path in ['/sdcard/apps/local.nurserysongs/data/player.json',
                     '/sdcard/apps/local.nurserysongs/data/play-mode.json',
                     '/sdcard/apps/local.audiobook/data/player.json',
                     '/sdcard/apps/local.audiobook/data/play-mode.json',
                     '/littlefs/audiobook-bookmark.json', '/littlefs/audiobook-play-mode.json']:
            saved[path] = f('Storage', 'FSReadText', {'Path': path}) if f('Storage', 'FSStat', {'Path': path})['exists'] else None
        recovery = {'modes': before, 'book': original_book, 'files': saved,
                    'original_app': current, 'apps': versions}
        (folder / 'recovery.json').write_text(json.dumps(recovery, ensure_ascii=False, indent=2), encoding='utf-8')
        owned_app = None
        ble_owned = False

        def stop_app():
            nonlocal owned_app
            if owned_app is not None:
                f('SystemCore', 'StopApp', {'AppId': owned_app})
                owned_app = None
            f('Audiobook', 'Stop')

        def start_app(name):
            nonlocal owned_app
            f('DeviceModes', 'Wake')
            owned_app = ids[name]
            f('SystemCore', 'StartApp', {'AppId': ids[name]})
            active = f('SystemCore', 'GetActiveApp')
            assert active['app_id'] == owned_app and active['state'] == 'Running' and not active['last_error']

        try:
            if current.get('app_id') and current['app_id'] != 1:
                f('SystemCore', 'StopApp', {'AppId': current['app_id']})
            f('DeviceModes', 'SetAutoDeepSleep', {'Minutes': 0})
            f('AudioPlayback', 'SetVolume', {'Volume': 0})
            report.update(status='running', started_at=datetime.now(TZ).isoformat(),
                          expected_end_at=(datetime.now(TZ) + timedelta(minutes=args.minutes)).isoformat(),
                          firmware=before['firmware_version'], app_count=len(apps))
            save()
            print(json.dumps({'event': 'started', 'report': str(folder / 'status.json'),
                              'end': report['expected_end_at']}, ensure_ascii=False), flush=True)
            started = time.monotonic()
            total = args.minutes * 60
            phase = -1
            previous_path = None
            ended_since = None
            last_ble = 0
            next_switch = 0
            switch_at = 0
            next_heartbeat = 0
            targets = ['local.weather', 'local.flipclock', 'local.codex.quota',
                       'local.virtualpet', 'local.gravitymaze']
            with (folder / 'samples.jsonl').open('w', encoding='utf-8') as samples:
                while time.monotonic() - started < total:
                    elapsed = time.monotonic() - started
                    if stop_file.exists():
                        report['status'] = 'stopped_by_request'
                        break
                    assert not f('ChildMode', 'GetState')['enabled'], 'Parent policy changed; stopping diagnostics'
                    selected = 3 if args.workload == 'apps' else min(3, int(elapsed / (total / 4)))
                    if selected != phase:
                        stop_app()
                        f('Audiobook', 'SetSleepTimer', {'Minutes': 0})
                        phase = selected
                        previous_path = None
                        ended_since = None
                        detail = {'phase': phase, 'at_seconds': round(elapsed),
                                  'name': ['nursery_sequence', 'lullaby_random_and_sleep',
                                           'story_sequence', 'app_switching'][phase],
                                  'transitions': 0}
                        report['phases'].append(detail)
                        # Firmware deliberately refuses opening BLE while audio
                        # is busy. Open it in the idle interval, then exercise
                        # simultaneous playback without bypassing that policy.
                        if not ble_before['active'] and not ble_before.get('ble_connected'):
                            if ble_owned:
                                f('PhoneProvisioning', 'Stop')
                                until = time.monotonic() + 10
                                while time.monotonic() < until:
                                    b = f('PhoneProvisioning', 'GetState')
                                    if not b['active'] and not b.get('starting'):break
                                    time.sleep(.2)
                                ble_owned = False
                            try:
                                f('PhoneProvisioning', 'StartRemote')
                                ble_owned = True
                                until = time.monotonic() + 15
                                while time.monotonic() < until:
                                    b = f('PhoneProvisioning', 'GetState')
                                    if b['active']:break
                                    time.sleep(.2)
                                if not b['active']:issue('idle_ble_failed', phase=phase)
                                else:detail['ble_ready_before_audio'] = True
                            except RuntimeError:
                                issue('idle_ble_rejected', phase=phase)
                            last_ble = elapsed
                        if phase < 3:
                            tracks = [nursery, lullabies, stories][phase]
                            f('Audiobook', 'SetSongMode' if phase < 2 else 'SetPlayMode',
                              {'Mode': 'random' if phase == 1 else 'sequence'})
                            start_app('local.nurserysongs' if phase < 2 else 'local.audiobook')
                            f('Audiobook', 'SetSpeed', {'Speed': 1})
                            f('Audiobook', 'Play', {'Path': tracks[0]['path'], 'Position': 0})
                            if phase == 1 and total / 4 >= 1000:
                                f('Audiobook', 'SetSleepTimer', {'Minutes': 15})
                        print(json.dumps({'event': 'phase', **detail}), flush=True)
                        save()
                    if phase == 3 and elapsed >= next_switch:
                        stop_app()
                        after = f('DeviceModes', 'GetResourceUsage')
                        detail['after_stop_internal'] = after['internal_free_bytes']
                        detail['after_stop_psram'] = after['psram_free_bytes']
                        name = targets[switch_at % len(targets)]
                        detail['open_attempts'] = detail.get('open_attempts', 0) + 1
                        try:
                            start_app(name)
                            detail['opens'] = detail.get('opens', 0) + 1
                        except RuntimeError as error:
                            issue('app_open_failed', app=name, error=str(error))
                            detail['open_failures'] = detail.get('open_failures', 0) + 1
                            # Unload the failed document before trying another
                            # app. Keep the failure in the final verdict.
                            stop_app()
                        switch_at += 1
                        next_switch = elapsed + 30
                    s = state()
                    usage = f('DeviceModes', 'GetResourceUsage')
                    ble = f('PhoneProvisioning', 'GetState')
                    if phase == 3 and not s['active'] and elapsed - last_ble >= 300 and not ble_before['active'] and not ble_before.get('ble_connected'):
                        last_ble = elapsed
                        if ble_owned:
                            f('PhoneProvisioning', 'Stop')
                            ble_owned = False
                        elif not ble['active'] and not ble.get('starting'):
                            try:
                                f('PhoneProvisioning', 'StartRemote')
                                ble_owned = True
                                detail['ble_starts'] = detail.get('ble_starts', 0) + 1
                            except RuntimeError:
                                issue('ble_start_rejected', phase=phase)
                    if s['error']:
                        issue('audio_error', phase=phase, error=s['error'])
                    if phase < 3 and s['active'] and s.get('pcm_starvations', 0):
                        issue('pcm_starvation', phase=phase)
                    if phase < 3:
                        if previous_path is not None and s['path'] != previous_path:
                            detail['transitions'] += 1
                        previous_path = s['path']
                        if s['state'] == 'Ended':
                            if phase != 1 and s['path'] == tracks[-1]['path']:
                                f('Audiobook', 'Play', {'Path': tracks[0]['path'], 'Position': 0})
                                detail['explicit_playlist_restarts'] = detail.get('explicit_playlist_restarts', 0) + 1
                            else:
                                ended_since = ended_since or elapsed
                                if elapsed - ended_since > 15:
                                    issue('eof_not_advanced', phase=phase)
                                    # Keep the stress workload running after recording a
                                    # real failure. Never count driver recovery as an
                                    # automatic transition or restart after sleep.
                                    if not s.get('sleep_completed'):
                                        at = next((i for i, t in enumerate(tracks) if t['path'] == s['path']), -1)
                                        f('Audiobook', 'Play', {'Path': tracks[(at + 1) % len(tracks)]['path'], 'Position': 0})
                                        detail['test_driver_recoveries'] = detail.get('test_driver_recoveries', 0) + 1
                                        ended_since = None
                        else:
                            ended_since = None
                        if phase == 1:
                            if s.get('sleep_fading'):detail['fade_seen'] = True
                            if s['state'] == 'SleepEnded':detail['sleep_ended_seen'] = True
                            if detail.get('sleep_ended_seen') and s['active']:
                                issue('playback_restarted_after_sleep', phase=phase)
                    row = {'elapsed_s': round(elapsed, 2), 'phase': phase, 'resource': usage,
                           'ble': {k: ble.get(k) for k in ['active', 'ble_connected', 'largest_dma_block', 'dma_free_bytes', 'memory_rejections']},
                           'audio': {k: s.get(k) for k in ['state', 'position', 'active', 'bytes_written', 'pcm_starvations', 'write_gap_max_us', 'pcm_stack_free_min_bytes', 'sleep_gain_per_mille']}}
                    samples.write(json.dumps(row) + '\n')
                    samples.flush()
                    report['samples'] += 1
                    report['elapsed_seconds'] = round(time.monotonic() - started, 1)
                    report['last_sample'] = row
                    for key in ['internal_free_bytes', 'psram_free_bytes']:
                        target = key + '_minimum'
                        report[target] = min(report.get(target, usage[key]), usage[key])
                    save()
                    if elapsed >= next_heartbeat:
                        print(json.dumps({'event': 'heartbeat', 'elapsed_seconds': round(elapsed),
                                          'phase': phase, 'issues': len(report['issues']),
                                          'internal_free': usage['internal_free_bytes'],
                                          'psram_free': usage['psram_free_bytes']}), flush=True)
                        next_heartbeat = elapsed + 300
                    time.sleep(min(5, max(0, total - (time.monotonic() - started))))
                else:
                    report['status'] = 'finished'
        except BaseException as error:
            report.update(status='failed', failure_type=type(error).__name__, failure=str(error))
        finally:
            errors = []
            def restore(label, fn):
                try:fn()
                except Exception as error:errors.append({'operation': label, 'error': type(error).__name__})
            restore('stop_test_app', stop_app)
            restore('cancel_test_timer', lambda: f('Audiobook', 'SetSleepTimer', {'Minutes': 0}))
            if ble_owned:restore('stop_owned_ble', lambda: f('PhoneProvisioning', 'Stop'))
            for name, value in [('SetPlayMode', original_book['play_mode']), ('SetSongMode', original_book['song_play_mode'])]:
                restore(name, lambda name=name, value=value: f('Audiobook', name, {'Mode': value}))
            restore('speed', lambda: f('Audiobook', 'SetSpeed', {'Speed': original_book['speed']}))
            for path, data in saved.items():
                if data is not None:
                    restore('file', lambda path=path, data=data: f('Storage', 'FSWriteText', {'Path': path, 'Data': data}))
                else:
                    restore('new_file', lambda path=path: f('Storage', 'FSRemove', {'Path': path}) if f('Storage', 'FSStat', {'Path': path})['exists'] else None)
            restore('volume', lambda: f('AudioPlayback', 'SetVolume', {'Volume': before['resume_volume']}))
            restore('deep_sleep', lambda: f('DeviceModes', 'SetAutoDeepSleep', {'Minutes': before['auto_deep_sleep_minutes']}))
            report['restore_errors'] = errors
            report['preferences_restored'] = not errors
            report['finished_at'] = datetime.now(TZ).isoformat()
            report['passed'] = report['status'] == 'finished' and not report['issues'] and not errors
            save()
    print(json.dumps({'event': 'completed', 'passed': report['passed'], 'status': report['status'],
                      'issues': report['issues'], 'restored': report.get('preferences_restored')}), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
