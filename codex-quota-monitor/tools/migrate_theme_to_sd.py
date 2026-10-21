"""Stage, commit or restore this board's optional SD theme assets.

Programs, parent controls, fonts and a wallpaper fallback stay in Flash.
Commit replaces eight full PNG copies with compact matching Flash fallbacks
after verified staging and an SD-aware firmware reboot.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from quota_monitor.brookesia import StableUsbClient

FLASH='/littlefs/themes/cream-handdrawn-v1'
SD='/sdcard/themes/cream-handdrawn-v1'
NAMES={'settings.png','files.png','app-store.png','quota.png','weather.png','audiobook.png','flipclock.png','assistant.png','wallpaper.jpg'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['stage','commit','restore'])
    parser.add_argument('--theme',type=Path)
    parser.add_argument('--fallbacks',type=Path,help='Compact matching Flash icons, required for commit')
    parser.add_argument('--record',type=Path,default=ROOT/'runtime/sd-theme-migration.json')
    parser.add_argument('--port',default='COM5')
    args=parser.parse_args()
    if args.action=='stage' and not args.theme:parser.error('stage requires --theme')
    if args.action=='commit' and not args.fallbacks:parser.error('commit requires --fallbacks')
    fallback_files={}
    if args.action=='commit':
        fallback_files=json.loads((args.fallbacks/'manifest.json').read_text(encoding='utf-8'))['files']
        assert set(fallback_files)==NAMES-{'wallpaper.jpg'}
        for name,entry in fallback_files.items():
            data=(args.fallbacks/name).read_bytes()
            assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
    with StableUsbClient(args.port,timeout=30) as c:
        c.hello()
        def storage(name,params):return c.call('Storage',name,params)['result']
        def stat(path):return storage('FSStat',{'Path':path})
        def save(report):args.record.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if args.action=='stage':
            manifest=json.loads((args.theme/'theme.json').read_text(encoding='utf-8'))
            assert manifest['id']=='cream-handdrawn-v1' and set(manifest['files'])==NAMES
            for name,entry in manifest['files'].items():
                data=(args.theme/name).read_bytes()
                assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
                info=stat(FLASH+'/'+name);assert info['exists'] and info['size']==len(data)
            backup='/sdcard/resource-backups/'+datetime.now().strftime('%Y%m%d-%H%M%S')+'/cream-handdrawn-v1'
            report={'backup':backup,'files':manifest['files'],'capacity_before':storage('GetFileSystemCapacity',{'MountPoint':'/littlefs'}),'staged':False,'removed':[]}
            save(report)
            for folder in [backup,SD]:storage('FSMkdir',{'Path':folder})
            for name,entry in manifest['files'].items():
                for destination in [backup,SD]:
                    storage('FSCopyTree',{'From':FLASH+'/'+name,'To':destination+'/'+name,'Overwrite':True})
                    info=stat(destination+'/'+name);assert info['exists'] and info['size']==entry['bytes']
            report['staged']=True;save(report)
            print('Nine theme assets copied to SD and backed up. Reboot SD-aware firmware before commit.')
            return
        report=json.loads(args.record.read_text(encoding='utf-8'))
        assert report['staged'] and set(report['files'])==NAMES
        assert report['backup'].startswith('/sdcard/resource-backups/')
        if args.action=='restore':
            for name in NAMES:
                storage('FSCopyTree',{'From':report['backup']+'/'+name,'To':FLASH+'/'+name,'Overwrite':True})
            print('Flash theme copies restored; restart to refresh images.');return
        resources=c.call('SdResources','GetState',{})['result']
        assert resources['sd_resolutions']>0,'Restart first so actual GUI loads use SD'
        assert all(f['on_sd'] and f['exists'] for f in resources['files']),resources
        for name,entry in report['files'].items():
            for root in [SD,report['backup']]:
                info=stat(root+'/'+name);assert info['exists'] and info['size']==entry['bytes']
        # Retain the same artwork on missing-card boots, using only 23KB total.
        report['flash_fallbacks']=fallback_files
        for name in sorted(NAMES-{'wallpaper.jpg'}):
            c.transfer('put',args.fallbacks/name,'theme-fallback-stage/'+name,True)
            storage('FSRename',{'From':'/littlefs/usb/theme-fallback-stage/'+name,'To':FLASH+'/'+name})
            info=stat(FLASH+'/'+name);assert info['exists'] and info['size']==fallback_files[name]['bytes']
            save(report)
        report['capacity_after']=storage('GetFileSystemCapacity',{'MountPoint':'/littlefs'})
        save(report)
        print('SD theme with eight matching compact Flash fallback icons. Free bytes:',report['capacity_after']['free_bytes'])

if __name__=='__main__':main()
