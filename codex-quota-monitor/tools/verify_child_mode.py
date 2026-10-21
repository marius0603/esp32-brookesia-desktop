"""Exercise child policy on a fresh installation, before the parent sets a PIN.

Uses a temporary random PIN. Refuses an already configured device. A private,
Git-ignored recovery record is deleted after cleanup; no PIN is logged.
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from quota_monitor.brookesia import StableUsbClient

class Client(StableUsbClient):
    def read_json(self):
        while True:
            try:return super().read_json()
            except RuntimeError as e:
                message=str(e)
                if ('invalid device response:' in message and 'HalIface: : - [System] Reference count ' in message):
                    self.diagnostic_lines.append(message.encode());continue
                if ('invalid device response:' in message and 'indev_pointer_proc:' in message and 'lv_indev.c:' in message):
                    self.diagnostic_lines.append(message.encode());continue
                raise

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',default='COM5')
    parser.add_argument('--reboot-check',action='store_true')
    parser.add_argument('--cleanup',action='store_true',help='Remove interrupted diagnostic credentials only')
    args=parser.parse_args()
    report={}
    output=ROOT/'runtime/child-mode-verification.json'
    recovery=ROOT/'runtime/child-mode-test-only.json'
    def stash(value):recovery.write_text(json.dumps({'purpose':'diagnostic-only','pin':pin,'token':value}),encoding='utf-8')
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pin=f'{secrets.randbelow(1000000):06d}'
    wrong=f'{(int(pin)+1)%1000000:06d}'
    token=''
    if args.cleanup:
        credentials=json.loads(recovery.read_text(encoding='utf-8'))
        assert credentials['purpose']=='diagnostic-only'
        with Client(args.port,timeout=30) as c:
            c.hello()
            def call(name,params={}):return c.call('ChildMode',name,params)['result']
            state=call('GetState')
            if state['configured']:
                deadline=time.monotonic()+65
                while call('GetState')['locked_seconds']>0:
                    assert time.monotonic()<deadline
                    time.sleep(1)
                session=call('VerifyPin',{'Pin':credentials['pin']})['token']
                call('Configure',{'Token':session,'Settings':{'enabled':False,'daily_minutes':30,'night_enabled':False}})
                call('ResetUsage',{'Token':session});call('ClearPin',{'Token':session})
            recovery.unlink()
        print('Diagnostic PIN removed.');return
    def checked_denied(c,service,name,params):
        try:c.call(service,name,params)
        except RuntimeError:return
        raise AssertionError('Policy did not reject '+service+'.'+name)
    with Client(args.port,timeout=30) as c:
        c.hello()
        def call(name,params={}):return c.call('ChildMode',name,params)['result']
        before=call('GetState');assert not before['configured'] and not before['enabled'],'Parent PIN already configured; refusing test'
        stash('')
        report['before']=before
        old_volume=c.call('AudioPlayback','GetVolume',{})['result']
        token=call('SetupPin',{'Pin':pin})['token']
        stash(token)
        checked_denied(c,'ChildMode','SetupPin',{'Pin':wrong})
        checked_denied(c,'ChildMode','Configure',{'Token':'invalid','Settings':{'enabled':True}})
        checked_denied(c,'ChildMode','VerifyPin',{'Pin':wrong})
        token=call('VerifyPin',{'Pin':pin})['token']
        stash(token)
        call('Configure',{'Token':token,'Settings':{'enabled':True,'daily_minutes':1,'night_enabled':False,'max_volume':30}})
        apps=c.call('SystemCore','ListApps',{})['result']
        visible={a['manifest']['id'] for a in apps if a['manifest']['visible']}
        assert visible=={'local.audiobook','local.weather','local.flipclock','local.childmode'},visible
        report['child_visible_apps']=sorted(visible)
        for app in apps:
            if app['manifest']['id'] in ('local.codex.quota','brookesia.general.settings','brookesia.general.files','brookesia.general.app_store','local.voiceassistant'):
                checked_denied(c,'SystemCore','StartApp',{'AppId':app['app_id']})
        checked_denied(c,'VoiceAssistant','Connect',{})
        c.call('AudioPlayback','SetVolume',{'Volume':99})
        assert c.call('AudioPlayback','GetVolume',{})['result']==30
        report['unauthorized_settings_and_app_launches_blocked']=True
        report['volume_cap_passed']=True
        clock=next(a for a in apps if a['manifest']['id']=='local.flipclock')
        c.call('SystemCore','StartApp',{'AppId':clock['app_id']})
        deadline=time.monotonic()+75
        print('Testing the one-minute usage limit...',flush=True)
        while True:
            state=call('GetState')
            if state['resting']:break
            assert time.monotonic()<deadline,'Usage limit was not enforced'
            time.sleep(2)
        time.sleep(2)
        active=c.call('SystemCore','GetActiveApp',{})['result']
        assert active.get('app_id')!=clock['app_id'],active
        checked_denied(c,'SystemCore','StartApp',{'AppId':clock['app_id']})
        checked_denied(c,'Audiobook','TestTone',{})
        report['usage_limit_stops_and_blocks_apps']=True
        report['usage_state']=state
        token=call('VerifyPin',{'Pin':pin})['token']
        stash(token)
        call('ResetUsage',{'Token':token})
        call('Configure',{'Token':token,'Settings':{'night_enabled':True,'night_start':0,'night_end':23}})
        # If current local hour is 23, use the complementary overnight interval.
        state=call('GetState')
        if not state['resting']:call('Configure',{'Token':token,'Settings':{'night_start':23,'night_end':0}})
        assert call('GetState')['resting']
        checked_denied(c,'SystemCore','StartApp',{'AppId':clock['app_id']})
        call('Configure',{'Token':token,'Settings':{'night_enabled':False,'daily_minutes':30}})
        report['night_limit_passed']=True
        call('Lock',{'Token':token})
        checked_denied(c,'ChildMode','Configure',{'Token':token,'Settings':{'enabled':False}})
        report['revoked_parent_session_blocked']=True
        save()
    if args.reboot_check:
        python=ROOT.parent/'i6/python_env/idf6.0_py3.12_env/Scripts/python.exe'
        capture=subprocess.run([str(python),str(ROOT/'tools/capture_brookesia_boot.py'),'--reset','--seconds','38'],capture_output=True)
        (ROOT/'runtime/child-mode-persistence-boot-private.log').write_bytes(capture.stdout+capture.stderr)
        assert capture.returncode==0,'Reboot capture failed'
    with Client(args.port,timeout=30) as c:
        c.hello()
        def call(name,params={}):return c.call('ChildMode',name,params)['result']
        state=call('GetState');assert state['enabled'] and state['configured'] and not state['allow_assistant']
        token=call('VerifyPin',{'Pin':pin})['token']
        stash(token)
        report['preferences_and_pin_survived_restart']=bool(args.reboot_check)
        for _ in range(5):checked_denied(c,'ChildMode','VerifyPin',{'Pin':wrong})
        assert call('GetState')['locked_seconds']>0
        checked_denied(c,'ChildMode','VerifyPin',{'Pin':pin})
        report['five_failed_pins_trigger_lockout']=True
        call('Configure',{'Token':token,'Settings':{'enabled':False,'max_volume':30,'daily_minutes':30,'night_enabled':False,
              'allow_audiobook':True,'allow_weather':True,'allow_clock':True,'allow_assistant':False,'night_start':21,'night_end':8}})
        call('ResetUsage',{'Token':token})
        call('ClearPin',{'Token':token})
        recovery.unlink()
        c.call('AudioPlayback','SetVolume',{'Volume':old_volume})
        final=call('GetState');assert not final['configured'] and not final['enabled'] and final['locked_seconds']==0
        report['final']=final;report['test_pin_removed']=True
        save()
        print('Policy, volume, PIN, time limits and restart checks passed; parent PIN remains unset.',flush=True)

if __name__=='__main__':main()
