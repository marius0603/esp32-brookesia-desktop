"""Install the reviewed November story additions, retaining playback preferences.

Download/normalize privately first; source URLs, hashes and measurements are in
samples/stories/library-20261101.json. No firmware or app replacement is needed.
"""
import argparse,hashlib,json,time
from datetime import datetime
from pathlib import Path
from deploy_audiobook_sleep import StoryClient

ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',required=True)
    parser.add_argument('--audio-dir',type=Path,required=True)
    args=parser.parse_args()
    manifest=json.loads((ROOT/'samples/stories/library-20261101.json').read_text(encoding='utf-8'))
    assert manifest['remove_from_library']==['/sdcard/audiobooks/bedtime/01-xiaoma-yueliang.mp3']
    rows=manifest['stories'];assert len(rows)==11 and len({r['filename'] for r in rows})==11
    for row in rows:
        assert Path(row['filename']).name==row['filename'] and row['filename'].endswith('.mp3')
        row['local']=args.audio_dir/('normalized-'+row['title']+'.mp3')
        assert row['local'].stat().st_size==row['bytes']
        assert hashlib.sha256(row['local'].read_bytes()).hexdigest()==row['sha256']
        assert abs(row['loudness_lufs']+14)<=.35 and row['true_peak_dbtp']<=-.8
    report={'passed':False,'uploaded':[],'playback_checks':[],
            'backup':'/sdcard/resource-backups/story-library-'+datetime.now().strftime('%Y%m%d-%H%M%S')}
    output=ROOT/'codex-quota-monitor/runtime/story-library-deployment.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with StoryClient(args.port,timeout=35) as c:
        c.hello()
        def f(s,n,p=None):return c.call(s,n,p or {})['result']
        before=report['playback_before']=f('Audiobook','GetState')
        modes=f('DeviceModes','GetState')
        assert not before['sleep_active'],'Wait for the running sleep timer to finish'
        assert not modes['screen_locked'],'Unlock using the device before installation'
        report['tracks_before']=f('Audiobook','List')['tracks']
        before_paths={t['path'] for t in report['tracks_before']}
        targets={'/sdcard/audiobooks/bedtime/'+r['filename'] for r in rows}
        assert not before_paths & targets,'New story filename already exists; inspect before replacing'
        app=next(a for a in f('SystemCore','ListApps') if a['manifest']['id']=='local.audiobook')
        f('DeviceModes','Wake')
        f('SystemCore','StopApp',{'AppId':app['app_id']})
        f('Audiobook','Stop')
        saved={}
        for p in ('/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json'):
            saved[p]=f('Storage','FSReadText',{'Path':p}) if f('Storage','FSStat',{'Path':p})['exists'] else None
        report['saved_files']=saved;report['volume_before']=modes['resume_volume']
        save()
        try:
            f('DeviceModes','SetAutoDeepSleep',{'Minutes':0})
            for row in rows:
                print('Uploading '+row['title'],flush=True)
                result=c.transfer('put',row['local'],'sd-audiobooks/bedtime/'+row['filename'],False)
                assert result['ok'] and result['sha256']==row['sha256']
                path='/sdcard/audiobooks/bedtime/'+row['filename']
                assert f('Storage','FSStat',{'Path':path})['size']==row['bytes']
                report['uploaded'].append({'path':path,'sha256':row['sha256'],'bytes':row['bytes']});save()
            removed=[]
            for path in manifest['remove_from_library']:
                stat=f('Storage','FSStat',{'Path':path})
                if stat['exists']:
                    target=report['backup']+'/'+Path(path).name
                    f('Storage','FSCopyTree',{'From':path,'To':target,'Overwrite':False})
                    assert f('Storage','FSStat',{'Path':target})['size']==stat['size']
                    f('Storage','FSRemove',{'Path':path})
                    removed.append(path)
            report['removed']=removed;save()
            expected=(before_paths-set(manifest['remove_from_library']))|targets
            tracks=f('Audiobook','List')['tracks']
            assert {t['path'] for t in tracks}==expected
            for row in rows:
                assert next(t['title'] for t in tracks if t['path'].endswith('/'+row['filename']))==row['title']
            report['tracks_after']=tracks
            f('AudioPlayback','SetVolume',{'Volume':0})
            f('SystemCore','StartApp',{'AppId':app['app_id']})
            for track in tracks:
                f('Audiobook','Play',{'Path':track['path'],'Position':0})
                deadline=time.monotonic()+20
                while True:
                    state=f('Audiobook','GetState');assert not state['error'],state
                    if state['path']==track['path'] and state['state']=='Playing' and state['bytes_written']>=32768:break
                    assert time.monotonic()<deadline,'Story did not decode: '+track['path']
                    time.sleep(.2)
                report['playback_checks'].append({'path':track['path'],'title':state['title'],'bytes_written':state['bytes_written']})
                f('Audiobook','Stop');save();print('Decoded '+track['title'],flush=True)
            report['content_verified']=True
        finally:
            f('Audiobook','Stop')
            for path,data in saved.items():
                # A bookmark for the explicitly removed story must not survive.
                if data is not None and not (path.endswith('bookmark.json') and json.loads(data).get('path') in manifest['remove_from_library']):
                    f('Storage','FSWriteText',{'Path':path,'Data':data})
                elif f('Storage','FSStat',{'Path':path})['exists']:f('Storage','FSRemove',{'Path':path})
            f('SystemCore','StartApp',{'AppId':app['app_id']})
            if before['active'] and before['path'] in {t['path'] for t in f('Audiobook','List')['tracks']}:
                f('Audiobook','Play',{'Path':before['path'],'Position':before['position']})
                if before['state']=='Paused':f('Audiobook','Pause')
            f('AudioPlayback','SetVolume',{'Volume':report['volume_before']})
            f('DeviceModes','SetAutoDeepSleep',{'Minutes':modes['auto_deep_sleep_minutes']})
            report['volume_after']=f('AudioPlayback','GetVolume')
            report['play_mode_preserved']=f('Storage','FSReadText',{'Path':'/littlefs/audiobook-play-mode.json'})==saved['/littlefs/audiobook-play-mode.json'] if saved['/littlefs/audiobook-play-mode.json'] is not None else True
            assert report['play_mode_preserved']
            assert f('DeviceModes','GetState')['resume_volume']==report['volume_before']
            report['passed']=report.get('content_verified',False)
            save()
    print('Verified '+str(len(report['tracks_after']))+' stories; original playback and volume restored.',flush=True)

if __name__=='__main__':main()
