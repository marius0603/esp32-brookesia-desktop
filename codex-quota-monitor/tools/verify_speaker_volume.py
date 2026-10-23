"""Read ES8311 volume/mute registers while playing, then restore quiet hours."""
import argparse,json,time
from pathlib import Path
from verify_child_mode import Client
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--restore-volume',type=int);args=parser.parse_args()
    if args.restore_volume is not None and not 0<=args.restore_volume<=100:raise ValueError('Invalid restore volume')
    report={'passed':False}
    with Client('COM5',timeout=25) as c:
        c.hello()
        def call(s,f,p=None):return c.call(s,f,p or {})['result']
        before=call('DeviceModes','GetState');restore=before['resume_volume'] if args.restore_volume is None else args.restore_volume;report['settings_before']={k:before[k] for k in ('quiet_hours_enabled','quiet_start_minute','quiet_end_minute','manual_do_not_disturb','resume_volume')}
        try:
            call('DeviceModes','Wake')
            call('DeviceModes','SetQuietHours',{'Enabled':False,'StartMinute':before['quiet_start_minute'],'EndMinute':before['quiet_end_minute']})
            call('DeviceModes','SetDoNotDisturb',{'Enabled':False})
            app=next(a for a in call('SystemCore','ListApps') if a['manifest']['id']=='local.audiobook')
            call('SystemCore','StartApp',{'AppId':app['app_id']});time.sleep(1)
            call('Audiobook','Play',{'Path':'/sdcard/audiobooks/bedtime/01-xiaoma-yueliang.mp3','Position':0});time.sleep(.5)
            samples=[]
            for volume in (10,30,0):
                call('AudioPlayback','SetVolume',{'Volume':volume});time.sleep(.2)
                sample=call('DeviceModes','GetSpeakerVolume');samples.append(sample)
                assert sample['codec_open'] and sample['codec_volume']==volume,sample
                assert sample['mute_valid'] and sample['muted']==(volume==0),sample
                assert call('AudioPlayback','GetVolume')==volume
            assert samples[0]['dac_register_valid'] and samples[1]['dac_register_valid']
            assert samples[0]['dac_volume_register']<samples[1]['dac_volume_register'],samples
            report.update(passed=True,samples=samples)
        finally:
            call('AudioPlayback','SetVolume',{'Volume':restore})
            call('Audiobook','Stop')
            call('DeviceModes','SetQuietHours',{'Enabled':before['quiet_hours_enabled'],'StartMinute':before['quiet_start_minute'],'EndMinute':before['quiet_end_minute']})
            call('DeviceModes','SetDoNotDisturb',{'Enabled':before['manual_do_not_disturb']})
            time.sleep(.5)
            report['restored_volume']=call('DeviceModes','GetState')['resume_volume']
            assert report['restored_volume']==restore
            (ROOT/'runtime/speaker-volume-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'samples':report.get('samples'),'restored_volume':report.get('restored_volume')}))
if __name__=='__main__':main()
