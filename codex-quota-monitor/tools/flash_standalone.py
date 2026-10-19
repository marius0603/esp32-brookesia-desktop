"""Flash the standalone app only after a complete, device-verified backup exists."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import esptool

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    folder = Path((ROOT / 'runtime/verified-backup-path.txt').read_text(encoding='utf-8').strip()).resolve()
    if not folder.is_relative_to((ROOT / 'runtime/backups').resolve()):
        raise SystemExit('Backup must be within runtime/backups.')
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    original = folder / 'factory-full-16MB.bin'
    if not (manifest.get('complete') and manifest.get('device_verified')):
        raise SystemExit('No complete, verified backup.')
    if original.stat().st_size != 16 * 1024 * 1024 or hashlib.sha256(original.read_bytes()).hexdigest() != manifest['sha256']:
        raise SystemExit('Backup file verification failed.')
    build = ROOT / 'firmware/build'
    project = json.loads((build / 'project_description.json').read_text(encoding='utf-8'))
    if project['project_name'] != 'codex_quota_monitor' or project['project_version'] != '0.3.0':
        raise SystemExit('Build the 0.3.0 standalone project first, never the link-check fixture.')
    binary = build / 'codex_quota_monitor.bin'
    if any(p.stat().st_mtime > binary.stat().st_mtime for p in (ROOT / 'firmware/main').glob('*') if p.is_file()):
        raise SystemExit('Source changed after the build; rebuild first.')
    subprocess.run([
        sys.executable, str(ROOT / 'tools/esp-idf-v5.5.5/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py'),
        'generate', str(ROOT / 'firmware/nvs.csv'), str(build / 'quota-nvs.bin'), '0x10000',
    ], check=True)
    config = json.loads((build / 'flasher_args.json').read_text(encoding='utf-8'))
    files = {offset: (build / filename).resolve() for offset, filename in config['flash_files'].items()}
    if set(int(offset, 0) for offset in files) != {0, 0x8000, 0x10000}:
        raise SystemExit('Unexpected Flash layout.')
    files['0xf00000'] = build / 'quota-nvs.bin'
    esp = esptool.detect_chip(args.port, baud=115200)
    try:
        mac = ':'.join(f'{b:02x}' for b in esp.read_mac())
        if mac != manifest['mac'] or mac != '44:bd:8d:78:9f:d8' or esp.CHIP_NAME != 'ESP32-S3':
            raise SystemExit('Device does not match the verified backup.')
        if esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled():
            raise SystemExit('Protected device; refusing to flash.')
        flash_args = ['--chip', 'esp32s3', '--port', args.port, '--baud', '921600',
                      '--before', 'no_reset', '--after', 'hard_reset', 'write_flash']
        for key in ('flash_mode', 'flash_freq', 'flash_size'):
            flash_args.extend(['--' + key, config['flash_settings'][key]])
        for offset, path in sorted(files.items(), key=lambda item: int(item[0], 0)):
            flash_args.extend([offset, str(path)])
        print('Verified backup:', folder, flush=True)
        esptool.main(flash_args, esp=esp)
        result = {'firmware': project['project_version'], 'mac': mac, 'port': args.port,
                  'backup': str(folder), 'esptool_verified': True,
                  'files': {offset: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                            for offset, path in files.items()}}
        (ROOT / 'runtime/flash-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    finally:
        esp._port.close()

if __name__ == '__main__':
    main()
