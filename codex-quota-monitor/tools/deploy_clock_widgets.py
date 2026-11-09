"""Stage a clock update file-by-file on SD, hash-check, then switch directories.

Avoid the large temporary allocation of the device's whole-BPK installer.
Refuse unknown app-tree edits; retain the complete original directory for recovery.
Restart after this command to refresh the registered manifest.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import time
import zipfile
from maintenance_client import SharedPowerDiagnosticClient

ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = '/sdcard/apps/local.flipclock'


def archive(version):
    package = ROOT / f'packages/apps/local.flipclock.debug.{version}.bpk'
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        files = {name: z.read(name) for name in z.namelist()}
    for name in files:
        path = PurePosixPath(name)
        assert not path.is_absolute() and '..' not in path.parts and '\\' not in name
    manifest = json.loads(files['manifest.json'])
    assert manifest['package']['id'] == 'local.flipclock' and manifest['package']['version'] == version
    return package, files


def tree_hash(files):
    h = hashlib.sha256()
    for name, data in sorted(files.items()):
        h.update(name.encode('utf-8') + b'\0' + struct.pack('<Q', len(data)) + data)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM5')
    args = parser.parse_args()
    version = json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps']['local.flipclock']
    package, files = archive(version)
    stamp = str(time.time_ns())
    base = '/sdcard/resource-backups/clock-widgets-' + stamp
    ready, retired = base+'-ready', base+'-previous'
    folder = ROOT/'codex-quota-monitor/runtime'/('clock-widgets-'+stamp)
    folder.mkdir(parents=True)
    report = {'passed': False, 'staged': False, 'restart_required': True, 'version': version,
              'backup': retired, 'ready': ready, 'package_sha256': hashlib.sha256(package.read_bytes()).hexdigest(), 'files': []}
    report_file = ROOT/'codex-quota-monitor/runtime/clock-widgets-deployment.json'
    def save():
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with SharedPowerDiagnosticClient(args.port, timeout=35) as client:
        client.hello()
        def call(service, name, params=None):
            return client.call_timeout(service, name, params or {})['result']
        def inspect(path):
            return call('SdResources','InspectTree',{'Path':path})
        modes = call('DeviceModes','GetState')
        assert not modes['screen_locked']
        for service in ('Audiobook','Radio','VoiceAssistant','LocalVoice'):
            assert not call(service,'GetState')['active'], 'Finish active audio before update'
        apps = call('SystemCore','ListApps')
        app = next(a for a in apps if a['manifest']['id']=='local.flipclock')
        report['other_apps'] = {a['manifest']['id']:a['manifest']['version'] for a in apps if a['manifest']['id']!='local.flipclock'}
        report['volume'] = modes['resume_volume']
        call('SystemCore','StopApp',{'AppId':app['app_id']})
        previous_version = json.loads(call('Storage','FSReadText',{'Path':APP_ROOT+'/manifest.json'}))['package']['version']
        _, old_files = archive(previous_version)
        original = inspect(APP_ROOT)
        assert original['sha256'] == tree_hash(old_files), 'Unrecognized app edits; refusing to replace the directory'
        call('Storage','FSCopyTree',{'From':APP_ROOT,'To':ready,'Overwrite':False})
        assert inspect(ready) == original
        save()
        merged = dict(old_files)
        for number, (name, data) in enumerate(sorted(files.items(), key=lambda item:(item[0]=='manifest.json',item[0]))):
            if old_files.get(name) == data:
                continue
            local = folder / str(number)
            local.write_bytes(data)
            temporary = 'clock-widgets-'+stamp+'.bin'
            result = client.transfer('put', local, 'sd-themes/'+temporary, False)
            assert result['ok'] and result['sha256'] == hashlib.sha256(data).hexdigest()
            call('Storage','FSCopyTree',{'From':'/sdcard/themes/'+temporary,'To':ready+'/'+name,'Overwrite':True})
            call('Storage','FSRemove',{'Path':'/sdcard/themes/'+temporary})
            assert call('Storage','FSStat',{'Path':ready+'/'+name})['size'] == len(data)
            merged[name] = data
            report['files'].append(name)
            save()
            print('Staged '+name, flush=True)
        expected = tree_hash(merged)
        staged = inspect(ready)
        assert staged['sha256'] == expected and staged['files'] == len(merged)
        assert inspect(APP_ROOT) == original, 'Original changed during staging'
        call('SystemCore','StopApp',{'AppId':app['app_id']})
        call('Storage','FSRename',{'From':APP_ROOT,'To':retired})
        try:
            call('Storage','FSRename',{'From':ready,'To':APP_ROOT})
            assert inspect(APP_ROOT) == staged
        except BaseException:
            if call('Storage','FSStat',{'Path':APP_ROOT})['exists']:
                call('Storage','FSRename',{'From':APP_ROOT,'To':ready})
            call('Storage','FSRename',{'From':retired,'To':APP_ROOT})
            raise
        assert inspect(retired) == original
        report.update(staged=True,tree_sha256=expected,resource_files=len(merged))
        save()
    print('Clock tree published and hash-verified; restart to register '+version, flush=True)


if __name__ == '__main__':
    main()
