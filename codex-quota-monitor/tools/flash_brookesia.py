"""Flash only the evaluated S3-2.16 Brookesia build, after checking both backups."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import esptool

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parent/'esp-brookesia-v08/examples/system/super_s3_216'

def checked_backup(pointer, filename):
    folder=Path((ROOT/'runtime'/pointer).read_text(encoding='utf-8').strip()).resolve()
    if not folder.is_relative_to((ROOT/'runtime/backups').resolve()):
        raise SystemExit('Unexpected backup location')
    info=json.loads((folder/'manifest.json').read_text())
    data=(folder/filename).read_bytes()
    if not info.get('complete') or not info.get('device_verified') or len(data)!=16777216 or hashlib.sha256(data).hexdigest()!=info['sha256']:
        raise SystemExit('Backup verification failed')
    return info

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',required=True)
    parser.add_argument('--app-only', action='store_true', help='Preserve installed apps, resources and NVS')
    args=parser.parse_args()
    factory=checked_backup('verified-backup-path.txt','factory-full-16MB.bin')
    prior=checked_backup('verified-standalone-backup-path.txt','standalone-0.3.0-full-16MB.bin')
    if factory['mac']!=prior['mac']: raise SystemExit('Backups belong to different boards')
    build=PROJECT/'build'
    desc=json.loads((build/'project_description.json').read_text())
    if desc['project_name']!='brookesia_s3_216' or desc['project_version'] not in {'0.8.3-s3.1','0.8.3-s3.2','0.8.3-s3.3','0.8.3-s3.4','0.8.3-s3.5','0.8.3-s3.6','0.8.3-s3.7','0.8.3-s3.8','0.8.3-s3.9','0.8.3-s3.10','0.8.3-s3.11','0.8.3-s3.12','0.8.3-s3.13','0.8.3-s3.14','0.8.3-s3.15','0.8.3-s3.16','0.8.3-s3.17','0.8.3-s3.18'}:
        raise SystemExit('Unexpected build')
    config=json.loads((build/'flasher_args.json').read_text())
    if not any('littlefs_data' in filename for filename in config['flash_files'].values()):
        raise SystemExit('System resources image is missing')
    csv=build/'initial_nvs.csv'
    csv.write_text('key,type,encoding,value\nplatform,namespace,,\nversion,data,string,brookesia-0.8\n',encoding='ascii')
    nvs=build/'initial_nvs.bin'
    subprocess.run([sys.executable,str(ROOT/'tools/esp-idf-v5.5.5/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py'),
                    'generate',str(csv),str(nvs),'0x6000'],check=True)
    files={offset:(build/path).resolve() for offset,path in config['flash_files'].items()}
    if not args.app_only:
        files['0x9000']=nvs
    for path in files.values():
        if not path.is_relative_to(build.resolve()) or not path.is_file(): raise SystemExit('Invalid image path')
    esp=esptool.detect_chip(args.port,baud=115200)
    try:
        mac=':'.join(f'{b:02x}' for b in esp.read_mac())
        if esp.CHIP_NAME!='ESP32-S3' or mac!=factory['mac']: raise SystemExit('Wrong device')
        if esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled(): raise SystemExit('Protected device')
        if args.app_only:
            esp.flash_spi_attach(0)
            table = files['0x8000'].read_bytes()
            if esp.read_flash(0x8000, len(table)) != table:
                raise SystemExit('Partition table differs: app-only update cannot proceed')
            files = {offset: path for offset, path in files.items() if path.name == desc['app_bin']}
            if len(files) != 1:
                raise SystemExit('Expected exactly one application image')
        command=['--chip','esp32s3','--port',args.port,'--baud','921600','--before','no_reset','--after','hard_reset','write_flash']
        for key in ('flash_mode','flash_freq','flash_size'): command.extend(['--'+key,config['flash_settings'][key]])
        for offset,path in sorted(files.items(),key=lambda item:int(item[0],0)): command.extend([offset,str(path)])
        esptool.main(command,esp=esp)
        result={'system':'ESP-Brookesia 0.8','build':desc['project_version'],'mac':mac,'port':args.port,'esptool_verified':True,'app_only':args.app_only,
                'files':{offset:{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for offset,path in files.items()}}
        (ROOT/'runtime/brookesia-flash-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    finally:
        esp._port.close()

if __name__=='__main__':main()
