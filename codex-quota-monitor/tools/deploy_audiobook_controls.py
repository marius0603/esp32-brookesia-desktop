"""Install the compact Q-icon audiobook UI after the native screen-lock update."""
import argparse
import contextlib
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time
import zipfile

from deploy_audiobook_sleep import StoryClient

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    package = ROOT.parent / 'packages/apps/local.audiobook.debug.0.3.0.bpk'
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['package']['id'] == 'local.audiobook' and manifest['package']['version'] == '0.3.0'
        assert archive.read('res/images/launcher_icon.png') == (ROOT.parent / 'themes/cartoon-q-v1/flash-fallback/audiobook.png').read_bytes()
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    folder = ROOT / 'runtime' / ('audiobook-controls-' + stamp)
    folder.mkdir(parents=True)
    report = {'backup': '/sdcard/resource-backups/audiobook-controls-' + stamp,
        'package_sha256': hashlib.sha256(package.read_bytes()).hexdigest(), 'restart_required': True}
    with StoryClient(args.port, timeout=30) as client:
        client.hello()
        def call(service, function, params=None):
            return client.call(service, function, params or {})['result']
        modes = call('DeviceModes', 'GetState')
        assert 'screen_locked' in modes and modes['volume_keys_ready'], 'Install screen-lock firmware first'
        assert not modes['screen_locked'], 'Double press volume+ to unlock before updating'
        call('DeviceModes', 'Wake')
        report['tracks_before'] = call('Audiobook', 'List')['tracks']
        before = report['playback_before'] = call('Audiobook', 'GetState')
        original_volume = call('AudioPlayback', 'GetVolume')
        restore_volume = modes['resume_volume'] if modes['do_not_disturb'] else original_volume
        app = next(a for a in call('SystemCore', 'ListApps') if a['manifest']['id'] == 'local.audiobook')
        call('Storage', 'FSCopyTree', {'From': '/littlefs/apps/local.audiobook', 'To': report['backup'], 'Overwrite': False})
        call('SystemCore', 'StopApp', {'AppId': app['app_id']})
        with (folder / 'install.log').open('w', encoding='utf-8') as log:
            with contextlib.redirect_stderr(log):
                installed = client.transfer('install_bpk', package, None, False)
        assert installed['ok'], installed
        app = next(a for a in call('SystemCore', 'ListApps') if a['manifest']['id'] == 'local.audiobook')
        assert app['manifest']['version'] == '0.3.0'
        call('SystemCore', 'StartApp', {'AppId': app['app_id']})
        active = call('SystemCore', 'GetActiveApp')
        assert active['app_id'] == app['app_id'] and active['state'] == 'Running' and not active['last_error'], active
        report['tracks_after'] = call('Audiobook', 'List')['tracks']
        assert report['tracks_after'] == report['tracks_before']
        if before['active'] and before['path']:
            try:
                call('AudioPlayback', 'SetVolume', {'Volume': 0})
                call('Audiobook', 'Play', {'Path': before['path'], 'Position': before['position']})
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    state = call('Audiobook', 'GetState')
                    if state['error']:
                        raise RuntimeError(state['error'])
                    if state['state'] == 'Playing' and state['position'] >= before['position'] and state['bytes_written']:
                        break
                    time.sleep(.2)
                else:
                    raise RuntimeError('Restored story did not decode')
                if before['state'] == 'Paused':
                    call('Audiobook', 'Pause')
                    call('Audiobook', 'Seek', {'Seconds': before['position']})
            finally:
                call('AudioPlayback', 'SetVolume', {'Volume': restore_volume})
        time.sleep(1.2)
        report.update(complete=True, active=call('SystemCore', 'GetActiveApp'),
            playback_after=call('Audiobook', 'GetState'), modes_after=call('DeviceModes', 'GetState'))
        (folder / 'deployment.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Audiobook 0.3.0 opened; stories and volume preserved. Restart once to refresh the cached launcher icon.', flush=True)

if __name__ == '__main__':
    main()
