"""Install song UI and calibrated media on SD; retain existing story preferences.

Requires app-only s3.47 firmware first. Transfers verify device SHA256. Reports
remain in ignored runtime storage; interrupted uploads can resume known files.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
from maintenance_client import MaintenanceClient

ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',default='COM5')
    p.add_argument('--audio-dir',type=Path,required=True)
    p.add_argument('--manifest',type=Path,default=ROOT/'samples/songs/library-20261104.json')
    a=p.parse_args();m=json.loads(a.manifest.read_text(encoding='utf-8'))
    assert m['device_root']=='/sdcard/audiobooks/songs' and len(m['songs'])==m['expected_total']==20
    for r in m['songs']:
        assert Path(r['filename']).name==r['filename'] and r['filename'].endswith('.mp3')
        local=a.audio_dir/('normalized-'+r['filename'])
        assert hashlib.sha256(local.read_bytes()).hexdigest()==r['sha256'] and local.stat().st_size==r['bytes']
        assert abs(r['loudness_lufs']-m['target_lufs'])<=.35 and r['true_peak_dbtp']<=-.8
    output=ROOT/'codex-quota-monitor/runtime/nursery-songs-deployment.json'
    report=json.loads(output.read_text(encoding='utf-8')) if output.exists() else {'uploaded':[],'backup':'/sdcard/resource-backups/nursery-songs-'+str(int(time.time()))}
    report.update(passed=False,manifest_sha256=hashlib.sha256(a.manifest.read_bytes()).hexdigest())
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with MaintenanceClient(a.port,timeout=35) as c:
        c.hello()
        def f(s,n,p=None):return c.call_timeout(s,n,p or {})['result']
        before=f('DeviceModes','GetState');book=f('Audiobook','GetState')
        assert before['firmware_version']=='0.8.3-s3.47','Install matching firmware first'
        assert not book['active'] and not book['sleep_active'] and not f('Radio','GetState')['active']
        assert not f('VoiceAssistant','GetState').get('active',False)
        stories=f('Audiobook','List')['tracks'];apps=f('SystemCore','ListApps')
        originals={r['manifest']['id']:r['manifest']['version'] for r in apps if r['manifest']['id'] not in ['local.nurserysongs','local.childmode']}
        saved={}
        for path in ['/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json']:
            saved[path]=f('Storage','FSReadText',{'Path':path}) if f('Storage','FSStat',{'Path':path})['exists'] else None
        report.update(story_count_before=len(stories),volume_before=before['resume_volume'])
        f('DeviceModes','Wake');f('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
        try:
            for app in apps:
                if app['manifest']['id']!='brookesia.system.super.shell' and app['state'] in ['Running','Paused','Starting']:
                    f('SystemCore','StopApp',{'AppId':app['app_id']})
            for r in m['songs']:
                target=m['device_root']+'/'+r['filename']
                exists=f('Storage','FSStat',{'Path':target})
                known=next((v for v in report['uploaded'] if v['path']==target and v['sha256']==r['sha256'] and v['bytes']==exists.get('size')),None)
                if exists['exists']:
                    assert known,'Unknown existing song; inspect before replacing '+target
                    print('Keeping '+r['title'],flush=True);continue
                print('Uploading '+r['title'],flush=True)
                result=c.transfer('put',a.audio_dir/('normalized-'+r['filename']),'sd-audiobooks/songs/'+r['filename'],False)
                assert result['ok'] and result['sha256']==r['sha256']
                assert f('Storage','FSStat',{'Path':target})['size']==r['bytes']
                report['uploaded'].append({'path':target,'sha256':r['sha256'],'bytes':r['bytes']});save()
            font=ROOT/'platform/super_s3_216/littlefs/system/fonts/audiobook-title-extra.ttf'
            target='/littlefs/system/fonts/audiobook-title-extra.ttf'
            f('Storage','FSMkdir',{'Path':report['backup']})
            backup=report['backup']+'/title-before.ttf'
            if not f('Storage','FSStat',{'Path':backup})['exists']:
                f('Storage','FSCopyTree',{'From':target,'To':backup,'Overwrite':False})
            stage_name='nursery-title-'+str(time.time_ns())+'.ttf'
            stage='sd-themes/'+stage_name
            result=c.transfer('put',font,stage,False);assert result['ok'] and result['sha256']==hashlib.sha256(font.read_bytes()).hexdigest()
            f('Storage','FSCopyTree',{'From':'/sdcard/themes/'+stage_name,'To':target,'Overwrite':True})
            assert f('Storage','FSStat',{'Path':target})['size']==font.stat().st_size
            f('Storage','FSRemove',{'Path':'/sdcard/themes/'+stage_name})
            for id,version in [('local.childmode','0.1.2'),('local.nurserysongs','0.1.0')]:
                old=next((r for r in apps if r['manifest']['id']==id),None)
                if old:
                    backup=report['backup']+'/'+id
                    if not f('Storage','FSStat',{'Path':backup})['exists']:
                        root=('/littlefs/apps/' if id=='local.childmode' else '/sdcard/apps/')+id
                        f('Storage','FSCopyTree',{'From':root,'To':backup,'Overwrite':False})
                package=ROOT/('packages/apps/'+id+'.debug.'+version+'.bpk')
                result=c.transfer('install_bpk',package,None,False);assert result['ok']
            after=f('SystemCore','ListApps')
            assert {r['manifest']['id']:r['manifest']['version'] for r in after if r['manifest']['id'] not in ['local.nurserysongs','local.childmode']}==originals
            assert f('Audiobook','List')['tracks']==stories,'Story library must stay separate and unchanged'
            songs=f('Audiobook','ListSongs')['tracks']
            assert {r['path'] for r in songs}=={m['device_root']+'/'+r['filename'] for r in m['songs']}
            for path,data in saved.items():
                if data is not None:assert f('Storage','FSReadText',{'Path':path})==data
            report.update(passed=True,song_count=len(songs),app_count=len(after),restart_for_font=True)
        finally:
            f('DeviceModes','SetAutoDeepSleep',{'Minutes':before['auto_deep_sleep_minutes']})
            assert f('DeviceModes','GetState')['resume_volume']==before['resume_volume']
            save()
    print('Installed 20 calibrated songs; story library and volume preserved. Restart for title font.',flush=True)

if __name__=='__main__':main()
