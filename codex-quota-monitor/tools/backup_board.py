"""Read-only full Flash backup, verified against the device before any replacement."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import esptool

ROOT = Path(__file__).resolve().parents[1]
SIZE = 16 * 1024 * 1024

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True)
    parser.add_argument('--label', choices=['factory', 'standalone-0.3.0'], default='factory')
    args = parser.parse_args()
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
    folder = ROOT / 'runtime/backups' / (stamp + '-44bd8d789fd8-' + args.label)
    folder.mkdir(parents=True, exist_ok=False)
    esp = esptool.detect_chip(args.port, baud=115200)
    try:
        mac = ':'.join(f'{b:02x}' for b in esp.read_mac())
        if esp.CHIP_NAME != 'ESP32-S3' or mac != '44:bd:8d:78:9f:d8':
            raise SystemExit('Unexpected device; no Flash writes performed.')
        if esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled():
            raise SystemExit('Protected device; no Flash writes performed.')
        esp = esp.run_stub()
        esp.change_baud(921600)
        esp.flash_spi_attach(0)
        flash_id = esp.flash_id()
        if (flash_id >> 16) != 0x18:
            raise SystemExit(f'Unexpected Flash capacity: {flash_id:#x}')
        esp.flash_set_parameters(SIZE)
        full = folder / (args.label + '-full-16MB.bin')
        with full.open('xb') as output:
            for offset in range(0, SIZE, 1024 * 1024):
                # esptool validates the stub's transfer digest on every read.
                data = esp.read_flash(offset, 1024 * 1024)
                assert len(data) == 1024 * 1024
                output.write(data)
                output.flush()
                progress = {'bytes': offset + len(data), 'total': SIZE, 'percent': (offset + len(data)) * 100 // SIZE}
                (folder / 'progress.json').write_text(json.dumps(progress), encoding='utf-8')
                print(f"Backup {progress['percent']}%", flush=True)
        data = full.read_bytes()
        device_md5 = esp.flash_md5sum(0, SIZE)
        if len(data) != SIZE or hashlib.md5(data).hexdigest() != device_md5.lower():
            raise SystemExit('Full device MD5 verification failed; backup is not authorized for flashing.')
        manifest = {
            'complete': True, 'device_verified': True, 'mac': mac, 'port': args.port,
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'device_md5': device_md5, 'flash_id': hex(flash_id), 'flash_written': False,
            'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        }
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        pointer = 'verified-backup-path.txt' if args.label == 'factory' else 'verified-standalone-backup-path.txt'
        (ROOT / 'runtime' / pointer).write_text(str(folder), encoding='utf-8')
        print('Verified complete backup:', full, flush=True)
    finally:
        try:
            esp.hard_reset()
        finally:
            esp._port.close()

if __name__ == '__main__':
    main()
