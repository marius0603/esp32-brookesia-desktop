"""Back up the current 16 MB S3 image without relabeling it as factory firmware."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

import esptool

ROOT = Path(__file__).resolve().parents[1]
SIZE = 16 * 1024 * 1024

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True)
    parser.add_argument('--label', default='pre-update')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', args.label):
        parser.error('Use a short ASCII label without path separators')
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
    folder = ROOT / 'runtime/backups' / (stamp + '-' + args.label)
    folder.mkdir(parents=True, exist_ok=False)
    esp = esptool.detect_chip(args.port, baud=115200)
    try:
        mac = ':'.join(f'{b:02x}' for b in esp.read_mac())
        if esp.CHIP_NAME != 'ESP32-S3' or esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled():
            raise SystemExit('Expected an unprotected ESP32-S3; no Flash writes performed')
        esp = esp.run_stub()
        esp.change_baud(921600)
        esp.flash_spi_attach(0)
        if esp.flash_id() >> 16 != 0x18:
            raise SystemExit('Expected 16 MB Flash; no Flash writes performed')
        esp.flash_set_parameters(SIZE)
        image = folder / (args.label + '-full-16MB.bin')
        with image.open('xb') as output:
            for offset in range(0, SIZE, 1024 * 1024):
                data = esp.read_flash(offset, 1024 * 1024)
                assert len(data) == 1024 * 1024
                output.write(data)
                output.flush()
                print('Backup:', (offset + len(data)) * 100 // SIZE, '%', flush=True)
        data = image.read_bytes()
        device_md5 = esp.flash_md5sum(0, SIZE).lower()
        if len(data) != SIZE or hashlib.md5(data).hexdigest() != device_md5:
            raise SystemExit('Device readback verification failed')
        manifest = {'complete': True, 'device_verified': True, 'mac': mac, 'bytes': SIZE,
            'sha256': hashlib.sha256(data).hexdigest(), 'device_md5': device_md5,
            'flash_written': False, 'purpose': 'Current firmware backup before app-only update',
            'image': image.name, 'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat()}
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        (ROOT / 'runtime/current-firmware-backup-path.txt').write_text(str(folder), encoding='utf-8')
        print('Verified current-firmware backup:', folder, flush=True)
    finally:
        try:
            esp.hard_reset()
        finally:
            esp._port.close()

if __name__ == '__main__':
    main()
