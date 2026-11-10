"""Add ten calibrated lullabies and stage the song app on SD without whole-BPK allocation."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile
from deploy_clock_widgets import tree_hash
from maintenance_client import SharedPowerDiagnosticClient

ROOT=Path(__file__).resolve().parents[2]
APP='/sdcard/apps/local.nurserysongs'


def package(version):
    path=ROOT/f'packages/apps/local.nurserysongs.debug.{version}.bpk'
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        result={name:archive.read(name) for name in archive.namelist()}
    for name in result:
        assert not name.startswith('/') and '..' not in name.split('/') and '\\' not in name
        assert name=='manifest.json' or name.startswith(('app/','res/'))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='COM5')
    parser.add_argument('--audio-dir',type=Path,required=True)
    args=parser.parse_args()
    manifest_path=ROOT/'samples/songs/lullabies-20261109.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    assert manifest['device_root']=='/sdcard/audiobooks/songs/lullabies' and len(manifest['songs'])==10
    for song in manifest['songs']:
        assert Path(song['filename']).name==song['filename']
        local=args.audio_dir/('normalized-'+song['filename'])
        assert hashlib.sha256(local.read_bytes()).hexdigest()==song['sha256'] and local.stat().st_size==song['bytes']
        assert abs(song['loudness_lufs']-manifest['target_lufs'])<=.35 and song['true_peak_dbtp']<=-.8
    version=json.loads((ROOT/'versions.json').read_text(encoding='utf-8'))['apps']['local.nurserysongs']
    files=package(version)
    output=ROOT/'codex-quota-monitor/runtime/lullabies-deployment.json'
    report=json.loads(output.read_text(encoding='utf-8')) if output.exists() else {'uploaded':[]}
    report.update(passed=False,version=version,manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest())
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with SharedPowerDiagnosticClient(args.port,timeout=35) as client:
        client.hello()
        def call(service,name,params=None):return client.call_timeout(service,name,params or {})['result']
        def inspect(path):return call('SdResources','InspectTree',{'Path':path})
        modes=call('DeviceModes','GetState')
        for service in ('Audiobook','Radio','VoiceAssistant','LocalVoice'):
            assert not call(service,'GetState')['active'],'Finish active audio before installing'
        apps=call('SystemCore','ListApps');app=next(a for a in apps if a['manifest']['id']=='local.nurserysongs')
        report['other_apps']={a['manifest']['id']:a['manifest']['version'] for a in apps if a['manifest']['id']!='local.nurserysongs'}
        report['stories_before']=call('Audiobook','List')['tracks']
        report['songs_before']=call('Audiobook','ListSongs')['tracks']
        report['volume']=modes['resume_volume']
        call('DeviceModes','Wake');call('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
        try:
            active=call('SystemCore','GetActiveApp')
            if active.get('app_id') and active.get('app_id')!='brookesia.system.super.shell':
                call('SystemCore','StopApp',{'AppId':active['app_id']})
            call('SystemCore','StopApp',{'AppId':app['app_id']})
            for song in manifest['songs']:
                target=manifest['device_root']+'/'+song['filename']
                existing=call('Storage','FSStat',{'Path':target})
                if existing['exists']:
                    assert any(v['path']==target and v['sha256']==song['sha256'] and v['bytes']==existing['size'] for v in report['uploaded']),'Unknown existing recording: '+target
                    print('Keeping '+song['title'],flush=True);continue
                result=client.transfer('put',args.audio_dir/('normalized-'+song['filename']),'sd-audiobooks/songs/lullabies/'+song['filename'],False)
                assert result['ok'] and result['sha256']==song['sha256']
                assert call('Storage','FSStat',{'Path':target})['size']==song['bytes']
                report['uploaded'].append({'path':target,'bytes':song['bytes'],'sha256':song['sha256']});save()
                print('Uploaded and hash-verified '+song['title'],flush=True)
            credit='Lullabies / 摇篮曲\nArtist: Alexander Blu — Orange Free Sounds\nFor personal noncommercial device use.\nChanges: translated display titles, mono MP3 conversion and loudness matching.\n\n'
            for song in manifest['songs']:
                credit+=f"{song['title']} / {song['original_title']}\n{song['page']}\n{song['license']}: {song['license_url']}\n\n"
            call('Storage','FSWriteText',{'Path':manifest['device_root']+'/CREDITS.txt','Data':credit})
            assert call('Storage','FSReadText',{'Path':manifest['device_root']+'/CREDITS.txt'})==credit
            previous=json.loads(call('Storage','FSReadText',{'Path':APP+'/manifest.json'}))['package']['version']
            if previous!=version:
                old_files=package(previous)
                for folder in ('app','res'):
                    subset={n[len(folder)+1:]:d for n,d in old_files.items() if n.startswith(folder+'/')}
                    assert inspect(APP+'/'+folder)['sha256']==tree_hash(subset),'Unrecognized application edits in '+folder
                stamp=str(time.time_ns());base='/sdcard/resource-backups/lullabies-'+stamp
                ready,retired=base+'-ready',base+'-previous'
                original=inspect(APP)
                call('Storage','FSCopyTree',{'From':APP,'To':ready,'Overwrite':False})
                assert inspect(ready)==original
                report.update(ready=ready,backup=retired,original=original);save()
                folder=ROOT/'codex-quota-monitor/runtime'/('lullaby-ui-'+stamp);folder.mkdir()
                for number,(name,data) in enumerate(sorted(files.items(),key=lambda item:(item[0]=='manifest.json',item[0]))):
                    if old_files.get(name)==data:continue
                    local=folder/str(number);local.write_bytes(data);temporary='lullaby-ui-'+stamp+'.bin'
                    result=client.transfer('put',local,'sd-themes/'+temporary,False)
                    assert result['ok'] and result['sha256']==hashlib.sha256(data).hexdigest()
                    call('Storage','FSCopyTree',{'From':'/sdcard/themes/'+temporary,'To':ready+'/'+name,'Overwrite':True})
                    call('Storage','FSRemove',{'Path':'/sdcard/themes/'+temporary})
                    assert call('Storage','FSStat',{'Path':ready+'/'+name})['size']==len(data)
                for name in ('app','res'):
                    subset={n[len(name)+1:]:d for n,d in files.items() if n.startswith(name+'/')}
                    assert inspect(ready+'/'+name)['sha256']==tree_hash(subset)
                for name in ('data','cache','files'):
                    if call('Storage','FSStat',{'Path':APP+'/'+name})['exists']:
                        assert inspect(APP+'/'+name)==inspect(ready+'/'+name),'Application data changed during staging'
                assert json.loads(call('Storage','FSReadText',{'Path':ready+'/manifest.json'}))==json.loads(files['manifest.json'])
                staged=inspect(ready);assert inspect(APP)==original
                call('Storage','FSRename',{'From':APP,'To':retired})
                try:
                    call('Storage','FSRename',{'From':ready,'To':APP})
                    assert inspect(APP)==staged
                except BaseException:
                    if call('Storage','FSStat',{'Path':APP})['exists']:call('Storage','FSRename',{'From':APP,'To':ready})
                    call('Storage','FSRename',{'From':retired,'To':APP});raise
                assert inspect(retired)==original
                report['tree_sha256']=staged['sha256']
            assert call('Audiobook','List')['tracks']==report['stories_before']
            songs=call('Audiobook','ListSongs')['tracks'];paths={t['path'] for t in songs}
            assert {manifest['device_root']+'/'+s['filename'] for s in manifest['songs']}<=paths
            assert {t['path'] for t in report['songs_before']}<=paths
            report.update(passed=True,song_count=len(songs),restart_required=True);save()
        finally:
            call('DeviceModes','SetAutoDeepSleep',{'Minutes':modes['auto_deep_sleep_minutes']})
            assert call('DeviceModes','GetState')['resume_volume']==modes['resume_volume']
    print('Ten lullabies and collection UI installed; restart to register '+version,flush=True)


if __name__=='__main__':main()
