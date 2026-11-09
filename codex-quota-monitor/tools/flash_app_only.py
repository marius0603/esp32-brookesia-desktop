"""Update only the built application; verify partition identity and protected bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import esptool

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='COM5')
    parser.add_argument('--project',type=Path,default=ROOT/'esp-brookesia-v08/examples/system/super_s3_216')
    parser.add_argument('--idf',type=Path,default=ROOT/'esp-idf-v6.0.2')
    args=parser.parse_args()
    build=args.project.resolve()/'build'
    desc=json.loads((build/'project_description.json').read_text(encoding='utf-8'))
    version=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['firmware']
    assert desc['project_name']=='brookesia_s3_216' and desc['target']=='esp32s3' and desc['project_version']==version
    image=(build/desc['app_bin']).resolve()
    assert image.parent==build and image.is_file()
    data=image.read_bytes()
    config=json.loads((build/'flasher_args.json').read_text(encoding='utf-8'))
    entries=[(int(offset,0),name) for offset,name in config['flash_files'].items() if Path(name).name==image.name]
    assert len(entries)==1
    offset=entries[0][0]
    sys.path.insert(0,str(args.idf.resolve()/'components/partition_table'))
    from gen_esp32part import PartitionTable
    table=(build/'partition_table/partition-table.bin').read_bytes()
    partitions=PartitionTable.from_binary(table)
    app=[p for p in partitions if p.type==0 and p.offset==offset]
    assert len(app)==1 and len(data)<=app[0].size
    part_end=offset+app[0].size
    backup=Path((ROOT/'codex-quota-monitor/runtime/current-firmware-backup-path.txt').read_text(encoding='utf-8').strip()).resolve()
    assert backup.is_relative_to((ROOT/'codex-quota-monitor/runtime/backups').resolve())
    record=json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
    saved=(backup/record['image']).read_bytes()
    assert record['complete'] and record['device_verified'] and len(saved)==record['bytes']==16*1024*1024
    assert hashlib.sha256(saved).hexdigest()==record['sha256']
    esp=esptool.detect_chip(args.port,baud=115200)
    try:
        mac=':'.join(f'{b:02x}' for b in esp.read_mac())
        assert esp.CHIP_NAME=='ESP32-S3' and mac==record['mac']=='44:bd:8d:78:9f:d8'
        assert not esp.get_secure_boot_enabled() and not esp.get_flash_encryption_enabled()
        esp=esp.run_stub();esp.change_baud(921600);esp.flash_spi_attach(0);esp.flash_set_parameters(len(saved))
        assert esp.read_flash(0x8000,len(table))==table,'Partition table changed; refusing update'
        protected=[(0,offset),(part_end,len(saved)-part_end)]
        before=[esp.flash_md5sum(start,size) for start,size in protected]
        settings=config['flash_settings']
        # The verified readback above already uploaded the stub. Do not upload
        # it again through the CLI wrapper onto its own resident RAM address.
        esptool.main(['--chip','esp32s3','--port',args.port,'--baud','921600','--no-stub','--before','no_reset','--after','no_reset',
                      'write_flash','--flash_mode',settings['flash_mode'],'--flash_freq',settings['flash_freq'],
                      '--flash_size',settings['flash_size'],hex(offset),str(image)],esp=esp)
        assert esp.flash_md5sum(offset,len(data)).lower()==hashlib.md5(data).hexdigest()
        after=[esp.flash_md5sum(start,size) for start,size in protected]
        assert before==after,'Protected Flash regions changed'
        report={'version':version,'app_only':True,'offset':hex(offset),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                'device_verified':True,'partition_table_unchanged':True,'protected_regions_unchanged':True,'backup':str(backup)}
        (ROOT/'codex-quota-monitor/runtime/app-only-update.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Application verified; all bytes outside the application partition unchanged.',flush=True)
    finally:
        try:esp.hard_reset()
        finally:esp._port.close()


if __name__=='__main__':main()
