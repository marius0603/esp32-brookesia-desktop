"""Back up and merge nine-grid resources; reboot with matching s3.51 firmware.

Preserves the 92px artwork, 112px touch areas, fonts, theme and image indexes.
Only three Flash JSON documents are changed. Private originals stay in runtime.
"""
import argparse,hashlib,json,time
from pathlib import Path
from maintenance_client import SharedPowerDiagnosticClient
from nine_grid_resources import prepare_documents,geometry,UNCHANGED

ROOT=Path(__file__).resolve().parents[2]
BASE='/littlefs/system/super/shell/'
NAMES=['constants/default.json','screens/app_launcher.json','templates/launcher_app_button.json']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',default='COM5');a=p.parse_args()
    folder=ROOT/'codex-quota-monitor/runtime'/('nine-grid-'+str(time.time_ns()));folder.mkdir(parents=True)
    report={'passed':False,'restart_required':True,'firmware_required':'0.8.3-s3.51','files':[]}
    def save(): (folder/'deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with SharedPowerDiagnosticClient(a.port,timeout=35) as c:
        c.hello()
        def f(s,n,v=None):
            print(s+'.'+n,flush=True)
            return c.call_timeout(s,n,v or {})['result']
        mode=f('DeviceModes','GetState');assert mode['firmware_version'] in ['0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54']
        assert not mode['screen_locked'] and not f('Audiobook','GetState')['active'] and not f('Audiobook','GetState')['sleep_active']
        assert not f('Radio','GetState')['active'] and not f('VoiceAssistant','GetState')['active']
        originals={name:f('Storage','FSReadText',{'Path':BASE+name}) for name in NAMES}
        for name,data in originals.items():
            path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(data,encoding='utf-8',newline='\n')
        updated=prepare_documents(*(json.loads(originals[name]) for name in NAMES))
        apps=f('SystemCore','ListApps');stories=f('Audiobook','List')['tracks'];songs=f('Audiobook','ListSongs')['tracks']
        report.update(apps_before={v['manifest']['id']:v['manifest']['version'] for v in apps},stories=len(stories),songs=len(songs),volume_before=mode['resume_volume'],geometry=geometry(sum(v['manifest']['visible'] for v in apps)))
        save();f('DeviceModes','Wake');f('PhoneProvisioning','Stop')
        end=time.monotonic()+15
        while f('PhoneProvisioning','GetState')['active']:
            assert time.monotonic()<end;time.sleep(.2)
        use_sd=any(v['available'] and v['root_path']=='/sdcard' for v in f('SystemCore','GetStorageLayout')['external'])
        try:
            for i,(name,doc) in enumerate(zip(NAMES,updated)):
                local=folder/('updated-'+str(i)+'.json');local.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8',newline='\n')
                stage='nine-grid-'+str(time.time_ns())+'.json'
                upload=('sd-themes/' if use_sd else '')+stage
                remote=('/sdcard/themes/' if use_sd else '/littlefs/usb/')+stage
                result=c.transfer('put',local,upload,False)
                assert result['ok'] and result['sha256']==hashlib.sha256(local.read_bytes()).hexdigest()
                f('Storage','FSCopyTree',{'From':remote,'To':BASE+name,'Overwrite':True})
                assert json.loads(f('Storage','FSReadText',{'Path':BASE+name}))==doc
                f('Storage','FSRemove',{'Path':remote});report['files'].append(name);save()
            assert f('Audiobook','List')['tracks']==stories and f('Audiobook','ListSongs')['tracks']==songs
            assert f('DeviceModes','GetState')['resume_volume']==mode['resume_volume']
            report.update(passed=True,icon_sizes_unchanged=UNCHANGED)
        except Exception:
            for name in NAMES:f('Storage','FSWriteText',{'Path':BASE+name,'Data':originals[name]})
            report['original_resources_restored']=True;raise
        finally:save()
    print('Nine-grid resources read back; original icon/template/font sizes retained. Reboot with s3.51.',flush=True)

if __name__=='__main__':main()
