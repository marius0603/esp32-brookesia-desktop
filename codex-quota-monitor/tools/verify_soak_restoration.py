"""Read back settings, bookmarks, catalogs and resources after a soak has exited.

Usage: python codex-quota-monitor/tools/verify_soak_restoration.py <run-folder>
Uses the run's private recovery file; never prints its saved preference contents.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'codex-quota-monitor/tools'))
from maintenance_client import SharedPowerDiagnosticClient

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('folder', type=Path)
parser.add_argument('--port', default='COM5')
args = parser.parse_args()
folder = args.folder
before = json.loads((folder / 'recovery.json').read_text(encoding='utf-8'))
run = json.loads((folder / 'status.json').read_text(encoding='utf-8'))
assert run['status'] in ('finished', 'failed', 'stopped_by_request'), 'Test still owns COM5'
checks = {}
with SharedPowerDiagnosticClient(args.port, timeout=35) as client:
    client.hello()
    def f(s, n, p=None):
        return client.call_timeout(s, n, p or {})['result']
    modes = f('DeviceModes', 'GetState')
    keys = ['firmware_version', 'desktop_theme_index', 'desktop_theme_saved_index',
            'auto_sleep_enabled', 'auto_deep_sleep_minutes', 'resume_volume',
            'manual_do_not_disturb', 'quiet_hours_enabled', 'quiet_start_minute',
            'quiet_end_minute', 'timezone']
    checks['mode_preferences_match'] = all(modes[k] == before['modes'][k] for k in keys)
    checks['mode_mismatch_keys'] = [k for k in keys if modes[k] != before['modes'][k]]
    book = f('Audiobook', 'GetState')
    checks['audio_preferences_match'] = all(book[k] == before['book'][k] for k in ['play_mode', 'song_play_mode', 'speed'])
    checks['test_audio_stopped'] = not book['active'] and not book['sleep_active']
    checks['saved_files_match'] = True
    for path, old in before['files'].items():
        exists = f('Storage', 'FSStat', {'Path': path})['exists']
        equal = (not exists) if old is None else exists and f('Storage', 'FSReadText', {'Path': path}) == old
        checks['saved_files_match'] &= bool(equal)
    versions = {a['manifest']['id']: a['manifest']['version'] for a in f('SystemCore', 'ListApps')}
    checks['app_versions_match'] = versions == before['apps']
    checks['app_count'] = len(versions)
    checks['stories'] = len(f('Audiobook', 'List')['tracks'])
    songs = f('Audiobook', 'ListSongs')['tracks']
    checks['nursery_songs'] = sum('/lullabies/' not in t['path'] for t in songs)
    checks['lullabies'] = sum('/lullabies/' in t['path'] for t in songs)
    checks['child_mode_unchanged'] = not f('ChildMode', 'GetState')['enabled']
    checks['panel_errors_before'] = before['modes']['panel_errors']
    checks['panel_errors_after'] = modes['panel_errors']
    checks['panel_errors_unchanged'] = checks['panel_errors_before'] == checks['panel_errors_after']
    checks['screen_sleep_count_before'] = before['modes']['sleep_count']
    checks['screen_sleep_count_after'] = modes['sleep_count']
    checks['resources_after'] = f('DeviceModes', 'GetResourceUsage')
    ble = f('PhoneProvisioning', 'GetState')
    checks['ble_after'] = {k: ble.get(k) for k in ['active', 'starting', 'ble_connected', 'start_attempts', 'memory_rejections', 'largest_dma_block', 'dma_free_bytes']}
    checks['active_app_after'] = f('SystemCore', 'GetActiveApp')
required = ['mode_preferences_match', 'audio_preferences_match', 'test_audio_stopped',
            'saved_files_match', 'app_versions_match', 'child_mode_unchanged', 'panel_errors_unchanged']
checks['passed'] = all(checks[k] for k in required) and (checks['stories'], checks['nursery_songs'], checks['lullabies']) == (30, 20, 10)
(folder / 'restoration-check.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(checks, ensure_ascii=False, indent=2))
raise SystemExit(0 if checks['passed'] else 1)
