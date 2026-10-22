"""Update only the Settings display resource after the s3.18 app-only flash."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time
from deploy_wallpaper_shift import WallpaperClient


def main():
    repo=Path(sys.argv[1]).resolve()
    source=repo/'platform/super_s3_216/overrides/settings-display.json'
    data=json.loads(source.read_text(encoding='utf-8'))
    assert any(n.get('id')=='deep_sleep_card' for n in data['children'][0]['children'])
    target='/littlefs/apps/brookesia.general.settings/res/screens/display.json'
    backup='/sdcard/resource-backups/deep-sleep-'+datetime.now().strftime('%Y%m%d-%H%M%S')
    with WallpaperClient('COM5',timeout=25) as c:
        c.hello()
        def call(s,f,p=None):return c.call(s,f,p or {})['result']
        apps=call('SystemCore','ListApps')
        app=next(a for a in apps if a['manifest']['id']=='brookesia.general.settings')
        call('SystemCore','RequestCloseApp',{'AppId':app['app_id']});time.sleep(1)
        call('Storage','FSMkdir',{'Path':backup})
        old=call('Storage','FSStat',{'Path':target});assert old['exists']
        call('Storage','FSCopyTree',{'From':target,'To':backup+'/display.json','Overwrite':False})
        assert call('Storage','FSStat',{'Path':backup+'/display.json'})['size']==old['size']
        c.transfer('put',source,'deep-sleep-display.json',True)
        call('Storage','FSRename',{'From':'/littlefs/usb/deep-sleep-display.json','To':target})
        assert call('Storage','FSStat',{'Path':target})['size']==source.stat().st_size
        print('Settings display updated; original backed up to SD',flush=True)
        report={'backup':backup,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
        (Path(__file__).resolve().parents[1]/'runtime/deep-sleep-deployment.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
