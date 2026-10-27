"""Back up and install the quota cards UI without changing firmware or quota data."""
import argparse
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
    version = json.loads((ROOT.parent / 'versions.json').read_text())['apps']['local.codex.quota']
    package = ROOT.parent / 'packages/apps' / ('local.codex.quota.debug.' + version + '.bpk')
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['package']['id'] == 'local.codex.quota'
        assert manifest['package']['version'] == version
    report = {'package_sha256': hashlib.sha256(package.read_bytes()).hexdigest(),
              'backup': '/sdcard/resource-backups/quota-cards-' + datetime.now().strftime('%Y%m%d-%H%M%S')}
    report_file = ROOT / 'runtime/quota-cards-install.json'
    def call(client, service, function, params=None):
        return client.call(service, function, params or {})['result']
    with StoryClient(args.port, timeout=30) as client:
        client.hello()
        call(client, 'DeviceModes', 'Wake')
        original = call(client, 'Storage', 'FSReadText', {'Path': '/littlefs/quota.json'})
        report['volume_before'] = call(client, 'AudioPlayback', 'GetVolume')
        app = next((a for a in call(client, 'SystemCore', 'ListApps') if a['manifest']['id'] == 'local.codex.quota'), None)
        if app and call(client, 'Storage', 'FSStat', {'Path': '/littlefs/apps/local.codex.quota'})['exists']:
            call(client, 'Storage', 'FSCopyTree', {'From': '/littlefs/apps/local.codex.quota',
                                                'To': report['backup'], 'Overwrite': False})
            if app['state'] in ('Running', 'Paused', 'Starting'):
                call(client, 'SystemCore', 'StopApp', {'AppId': app['app_id']})
        else:
            report['backup'] = None  # Also permits recovery after an interrupted uninstall.
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for attempt in range(3):
        try:
            with StoryClient(args.port, timeout=30) as client:
                client.hello()
                installed = client.transfer('install_bpk', package, None, False)
                assert installed['ok'], installed
            break
        except RuntimeError as exc:
            if attempt == 2 or 'Wait timeout after 5000 ms' not in str(exc):
                raise
            print('Waiting for asynchronous app cleanup before reconnecting.', flush=True)
            time.sleep(7)
    with StoryClient(args.port, timeout=30) as client:
        client.hello()
        app = next(a for a in call(client, 'SystemCore', 'ListApps') if a['manifest']['id'] == 'local.codex.quota')
        assert app['manifest']['version'] == version
        assert json.loads(call(client, 'Storage', 'FSReadText', {'Path': '/littlefs/apps/local.codex.quota/manifest.json'})) == manifest
        assert call(client, 'Storage', 'FSReadText', {'Path': '/littlefs/quota.json'}) == original
        report['quota_preserved'] = True
        call(client, 'SystemCore', 'StartApp', {'AppId': app['app_id']})
        time.sleep(3)
        active = call(client, 'SystemCore', 'GetActiveApp')
        assert active['app_id'] == app['app_id'] and active['state'] == 'Running' and not active['last_error'], active
        report['active'] = active
        report['volume_preserved'] = call(client, 'AudioPlayback', 'GetVolume') == report['volume_before']
        assert report['volume_preserved']
        report['passed'] = True
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Quota ' + version + ' running; original quota data and volume preserved.')


if __name__ == '__main__':
    main()
