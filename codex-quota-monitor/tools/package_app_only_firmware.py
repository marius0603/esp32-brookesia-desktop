"""Package the reviewed application plus a partition table used only for verification."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    desc = json.loads((build / 'project_description.json').read_text(encoding='utf-8'))
    versions = json.loads((ROOT / 'versions.json').read_text(encoding='utf-8'))
    assert desc['project_name'] == 'brookesia_s3_216' and desc['project_version'] == versions['firmware']
    config = json.loads((build / 'flasher_args.json').read_text(encoding='utf-8'))
    keep = {offset: name for offset, name in config['flash_files'].items()
        if Path(name).name == desc['app_bin'] or int(offset, 0) == 0x8000}
    assert len(keep) == 2 and any(int(k, 0) == 0x8000 for k in keep)
    slim = {key: config[key] for key in ('write_flash_args', 'flash_settings', 'extra_esptool_args')}
    slim['flash_files'] = keep
    description = {key: desc[key] for key in ('project_name', 'project_version', 'app_bin')}
    output = ROOT / 'packages/firmware' / ('brookesia-' + desc['project_version'] + '-app-only.zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'version': desc['project_version'], 'device': 'ESP32-S3-Touch-AMOLED-2.16',
        'app_only': True, 'files': {}}
    sdkconfig = json.loads((build / 'config/sdkconfig.json').read_text(encoding='utf-8'))
    manifest['features'] = {'separate_websocket_tx_lock': bool(sdkconfig.get('ESP_WS_CLIENT_SEPARATE_TX_LOCK'))}
    temporary = output.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        launcher=ROOT/'packages/resources/phone-launcher-s3.28.json'
        if desc['project_version']=='0.8.3-s3.28':
            data=launcher.read_bytes()
            archive.writestr('launcher/app_launcher.json',data)
            manifest['files']['launcher/app_launcher.json']={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
            manifest['features']['phone_launcher']=True
        for name in keep.values():
            path = (build / name).resolve()
            assert path.is_relative_to(build) and path.is_file()
            data = path.read_bytes()
            archive.writestr(Path(name).as_posix(), data)
            manifest['files'][name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        archive.writestr('flasher_args.json', json.dumps(slim, indent=2) + '\n')
        archive.writestr('project_description.json', json.dumps(description, indent=2) + '\n')
        archive.writestr('manifest.json', json.dumps(manifest, indent=2) + '\n')
        archive.writestr('README.txt',
            'App-only update for ESP32-S3-Touch-AMOLED-2.16.\n'
            'Use tools/backup_current_firmware.py first; keep its verified private backup.\n'
            'Extract this package, then run tools/update_brookesia_app_only.py with --port, --build and --backup.\n'
            'The partition table is included for comparison; the updater writes only the application.\n'
            'NVS, LittleFS, installed apps and SD contents are preserved.\n'
            'After reboot install the matching application packages described in the release documentation.\n')
    with zipfile.ZipFile(temporary) as archive:
        assert archive.testzip() is None
    temporary.replace(output)
    print(output)
    print('SHA256:', hashlib.sha256(output.read_bytes()).hexdigest())

if __name__ == '__main__':
    main()
