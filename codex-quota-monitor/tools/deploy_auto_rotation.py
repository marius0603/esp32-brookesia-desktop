"""Install the Settings rotation switch after an app-only s3.8 firmware flash.

The existing descriptor is backed up on SD before replacement. No app package,
theme image index, NVS or user audio is replaced.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quota_monitor.brookesia import StableUsbClient

TARGET = '/littlefs/apps/brookesia.general.settings/res/screens/display.json'
STAGE = '/littlefs/usb/rotation-stage/settings-display.json'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('asset', type=Path, nargs='?')
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--restore-from', help='SD descriptor path recorded by a previous deployment')
    args = parser.parse_args()
    if not args.restore_from and not args.asset:
        parser.error('Supply settings-display.json or --restore-from')
    if args.asset:
        doc = json.loads(args.asset.read_text(encoding='utf-8'))
        assert doc['id']=='display' and any(c['id']=='auto_rotation_card' for c in doc['children'][0]['children'])
    with StableUsbClient(args.port, timeout=25) as client:
        client.hello()
        def call(service, function, params):
            return client.call(service, function, params)['result']
        active = call('SystemCore','GetActiveApp',{})
        if active.get('manifest',{}).get('id') not in (None,'brookesia.system.super.shell'):
            call('SystemCore','RequestCloseApp',{'AppId':active['app_id']})
        call('Storage','FSMkdir',{'Path':'/littlefs/usb/rotation-stage'})
        if args.restore_from:
            assert args.restore_from.startswith('/sdcard/rotation-backups/')
            call('Storage','FSCopyTree',{'From':args.restore_from,'To':STAGE,'Overwrite':True})
        else:
            state=call('AutoRotation','GetState',{})
            assert state['available'],state
            backup='/sdcard/rotation-backups/'+datetime.now().strftime('%Y%m%d-%H%M%S')+'/display.json'
            call('Storage','FSMkdir',{'Path':backup.rsplit('/',1)[0]})
            call('Storage','FSCopyTree',{'From':TARGET,'To':backup,'Overwrite':False})
            report={'settings_backup':backup,'state_before':state,'asset_bytes':args.asset.stat().st_size}
            record=ROOT/'runtime/auto-rotation-deployment.json'
            record.parent.mkdir(exist_ok=True)
            record.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            client.transfer('put',args.asset,'rotation-stage/settings-display.json',True)
        call('Storage','FSRename',{'From':STAGE,'To':TARGET})
        if not args.restore_from:
            installed=json.loads(call('Storage','FSReadText',{'Path':TARGET}))
            assert installed==doc
            print('Settings switch installed. Backup:',backup)
        else:
            print('Previous Settings descriptor restored.')

if __name__=='__main__':
    main()
