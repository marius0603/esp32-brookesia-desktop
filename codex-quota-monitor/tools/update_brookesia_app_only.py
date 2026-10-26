"""Update only a verified application partition, keeping NVS and LittleFS intact."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import esptool
from esptool.cmds import write_flash

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    backup = args.backup.resolve()
    if not backup.is_relative_to((ROOT / 'runtime/backups').resolve()):
        raise SystemExit('Backup must be in the private runtime/backups directory')
    saved = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    image = (backup / saved['image']).resolve()
    if not image.is_relative_to(backup):
        raise SystemExit('Invalid backup image path')
    old = image.read_bytes()
    if not saved.get('complete') or not saved.get('device_verified') or len(old) != 16 * 1024 * 1024:
        raise SystemExit('A complete device-verified backup is required')
    if hashlib.sha256(old).hexdigest() != saved['sha256']:
        raise SystemExit('Backup checksum mismatch')
    description = json.loads((build / 'project_description.json').read_text(encoding='utf-8'))
    versions = json.loads((ROOT.parent / 'versions.json').read_text(encoding='utf-8'))
    if description['project_name'] != 'brookesia_s3_216' or description['project_version'] != versions['firmware']:
        raise SystemExit('Build does not match the reviewed firmware version')
    config = json.loads((build / 'flasher_args.json').read_text(encoding='utf-8'))
    files = {int(offset, 0): (build / path).resolve() for offset, path in config['flash_files'].items()}
    if any(not path.is_relative_to(build) or not path.is_file() for path in files.values()):
        raise SystemExit('Invalid build image path')
    applications = [(offset, path) for offset, path in files.items() if path.name == description['app_bin']]
    if len(applications) != 1 or 0x8000 not in files:
        raise SystemExit('Expected exactly one application and an explicit partition table')
    offset, app = applications[0]
    table = files[0x8000].read_bytes()
    if old[0x8000:0x8000 + len(table)] != table:
        raise SystemExit('Partition table differs from backup; no Flash writes performed')
    app_data = app.read_bytes()
    partitions = []
    for at in range(0, len(table) - 31, 32):
        magic, kind, subtype, address, size = struct.unpack_from('<HBBII', table, at)
        if magic == 0x50AA and kind == 0 and address == offset:
            partitions.append((address, size))
    if len(partitions) != 1 or len(app_data) > partitions[0][1]:
        raise SystemExit('Application does not fit its existing partition')
    esp = esptool.detect_chip(args.port, baud=115200)
    try:
        mac = ':'.join(f'{b:02x}' for b in esp.read_mac())
        if esp.CHIP_NAME != 'ESP32-S3' or mac != saved['mac']:
            raise SystemExit('Wrong device; no Flash writes performed')
        if esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled():
            raise SystemExit('Protected device; no Flash writes performed')
        esp = esp.run_stub()
        esp.change_baud(921600)
        esp.flash_spi_attach(0)
        if esp.read_flash(0x8000, len(table)) != table:
            raise SystemExit('Device partition table differs; no Flash writes performed')
        # Reuse the verified live stub; re-entering the CLI would upload a
        # second stub over the running one before any Flash write.
        write_flash(esp, [(offset, app_data)], no_progress=True,
            **config['flash_settings'])
        if esp.flash_md5sum(offset, len(app_data)).lower() != hashlib.md5(app_data).hexdigest():
            raise SystemExit('Application readback checksum mismatch')
        result = {'version': description['project_version'], 'app_only': True, 'offset': hex(offset),
            'bytes': len(app_data), 'sha256': hashlib.sha256(app_data).hexdigest(),
            'device_verified': True, 'partition_table_unchanged': True, 'backup': str(backup)}
        (ROOT / 'runtime/app-only-update.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print('Application verified; NVS and LittleFS preserved.', flush=True)
    finally:
        try:
            esp.hard_reset()
        finally:
            esp._port.close()

if __name__ == '__main__':
    main()
