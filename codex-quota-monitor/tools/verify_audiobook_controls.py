"""Verify the real sleep selector; optionally leave the device locked for key testing."""
import argparse
import json
from pathlib import Path
import time

from deploy_audiobook_sleep import StoryClient

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True)
    parser.add_argument('--lock', action='store_true', help='Lock for a physical double volume+ test')
    args = parser.parse_args()
    report = {'passed': False, 'physical_unlock_verified': False}
    with StoryClient(args.port, timeout=20) as client:
        client.hello()
        def call(service, function, params=None):
            return client.call(service, function, params or {})['result']
        def picker():
            layers = call('DeviceModes', 'GetWeatherLayers')['layers']
            return next(layer for layer in layers if layer['kind'] == 'sleep_picker')
        app = next(a for a in call('SystemCore', 'ListApps') if a['manifest']['id'] == 'local.audiobook')
        assert app['manifest']['version'] == '0.3.0'
        modes = call('DeviceModes', 'GetState')
        assert modes['firmware_version'] == '0.8.3-s3.23' and not modes['screen_locked']
        report['modes_before'] = modes
        report['playback_before'] = call('Audiobook', 'GetState')
        assert not report['playback_before']['sleep_active'], 'Keep the current sleep timer; test later'
        call('SystemCore', 'StartApp', {'AppId': app['app_id']})
        report['picker'] = picker()
        assert report['picker']['options'] == 4
        assert report['picker']['font_height'] > 20
        assert report['picker']['popup_font_height'] == report['picker']['font_height']
        assert report['picker']['selected_font_height'] == report['picker']['font_height']
        try:
            for selected, minutes in enumerate([0, 15, 30, 45]):
                call('Audiobook', 'SetSleepTimer', {'Minutes': minutes})
                deadline = time.monotonic() + 4
                while True:
                    visible = picker()
                    if visible['selected'] == selected:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Sleep selector did not reflect native timer')
                    time.sleep(.2)
                state = call('Audiobook', 'GetState')
                assert state['sleep_minutes'] == minutes and state['sleep_active'] == (minutes != 0)
            before = call('Audiobook', 'GetState')['sleep_remaining_seconds']
            time.sleep(2.2)
            after = call('Audiobook', 'GetState')['sleep_remaining_seconds']
            assert after < before, 'UI polling restarted or stalled the native countdown'
            report['timer_presets_and_sync'] = True
        finally:
            call('Audiobook', 'SetSleepTimer', {'Minutes': 0})
        icon = json.loads(call('Storage', 'FSReadText', {'Path': '/littlefs/apps/local.audiobook/res/images/index.json'}))
        launcher = next(i for i in icon['images'] if i['id'] == 'launcher_icon')
        assert launcher['src'] == 'launcher_icon.png' and launcher['width'] == launcher['height'] == 96
        expected = ROOT.parent / 'themes/cartoon-q-v1/flash-fallback/audiobook.png'
        assert call('Storage', 'FSStat', {'Path': '/littlefs/apps/local.audiobook/res/images/launcher_icon.png'})['size'] == expected.stat().st_size
        active = call('SystemCore', 'GetActiveApp')
        assert active['app_id'] == app['app_id'] and active['state'] == 'Running' and not active['last_error']
        report['tracks'] = call('Audiobook', 'List')['tracks']
        report['passed'] = True
        if args.lock:
            sound = call('DeviceModes', 'GetState')
            report['unlock_count_before'] = sound['screen_unlock_count']
            playing = call('Audiobook', 'GetState')
            tone = not playing['active']
            try:
                if tone:
                    call('AudioPlayback', 'SetVolume', {'Volume': 0})
                    call('Audiobook', 'TestTone')
                start = call('Audiobook', 'GetState')
                call('DeviceModes', 'LockScreen')
                deadline = time.monotonic() + 5
                while True:
                    state = call('DeviceModes', 'GetState')
                    if state['screen_locked'] and state['screen_asleep']:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Screen did not lock and sleep')
                    time.sleep(.1)
                time.sleep(2.3)
                finish = call('Audiobook', 'GetState')
                assert not finish['error'] and finish['bytes_written'] > start['bytes_written'], finish
                assert tone or finish['position'] >= start['position'], finish
                report['audio_continues_while_locked'] = True
                report['locked'] = call('DeviceModes', 'GetState')
            finally:
                if tone:
                    call('AudioPlayback', 'SetVolume', {'Volume': sound['resume_volume']})
            print('Locked. Touch must not wake the screen. Double press volume+ to unlock.', flush=True)
        (ROOT / 'runtime/audiobook-controls-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Native selector, countdown, Q icon and app state verified.', flush=True)

if __name__ == '__main__':
    main()
