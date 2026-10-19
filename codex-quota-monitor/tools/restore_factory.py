"""Restore this board from its verified private full backup. Run only on request."""
import argparse
import hashlib
import json
from pathlib import Path
import esptool

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True)
    parser.add_argument('--source', choices=['factory', 'standalone-0.3.0'], default='factory')
    args = parser.parse_args()
    pointer = 'verified-backup-path.txt' if args.source == 'factory' else 'verified-standalone-backup-path.txt'
    folder = Path((ROOT / 'runtime' / pointer).read_text(encoding='utf-8').strip()).resolve()
    if not folder.is_relative_to((ROOT / 'runtime/backups').resolve()):
        raise SystemExit('Unexpected backup location.')
    info = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    image = folder / (args.source + '-full-16MB.bin')
    if not (info.get('complete') and info.get('device_verified')):
        raise SystemExit('Backup verification record missing.')
    if image.stat().st_size != 16777216 or hashlib.sha256(image.read_bytes()).hexdigest() != info['sha256']:
        raise SystemExit('Backup file failed verification.')
    esp = esptool.detect_chip(args.port, baud=115200)
    try:
        mac = ':'.join(f'{b:02x}' for b in esp.read_mac())
        if esp.CHIP_NAME != 'ESP32-S3' or mac != info['mac']:
            raise SystemExit('This backup belongs to a different board.')
        if esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled():
            raise SystemExit('Protected device; refusing restoration.')
        esptool.main(['--chip', 'esp32s3', '--port', args.port, '--baud', '921600',
                      '--before', 'no_reset', '--after', 'hard_reset', 'write_flash',
                      '--flash_mode', 'keep', '--flash_freq', 'keep', '--flash_size', 'keep',
                      '0x0', str(image)], esp=esp)
    finally:
        esp._port.close()

if __name__ == '__main__':
    main()
