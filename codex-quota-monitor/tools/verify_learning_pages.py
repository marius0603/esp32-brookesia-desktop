"""Exercise real card rendering using a temporary app, then restore the release app."""
import argparse,json,time,zipfile
from pathlib import Path
from deploy_learning import install_app
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--port',required=True)
    args=p.parse_args()
    release=REPO/'packages/apps/local.lightlearning.debug.0.1.0.bpk'
    temporary=ROOT/'runtime/learning-page-test.bpk'
    # Use the real app actions and renderer, with four seconds between swipes.
    hook="""on_timer(){if(!hidden){globalThis.pageTestTicks=(globalThis.pageTestTicks||0)+1;
if(globalThis.pageTestTicks%16===4){globalThis.pageTestStep=(globalThis.pageTestStep||0)+1;
const step=globalThis.pageTestStep;if(step===1)choose('cards');
else if(step<=6)move(1);else if(step===7)choose('arithmetic');else if(step===8)choose('english');
if(step<=8)console.log('LEARNING_PAGE_OK:'+step);}}if(!hidden)"""
    with zipfile.ZipFile(release) as source,zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as dest:
        for name in source.namelist():
            data=source.read(name)
            if name=='app/main.js':
                text=data.decode();assert text.count('on_timer(){if(!hidden)')==1
                data=text.replace('on_timer(){if(!hidden)',hook).encode()
            dest.writestr(name,data)
    passed=False
    raw=bytearray()
    try:
        install_app(args.port,temporary)
        with StoryClient(args.port,timeout=25) as c:
            c.hello()
            apps=c.call('SystemCore','ListApps',{})['result']
            app=next(a for a in apps if a['manifest']['id']=='local.lightlearning')
            volume=c.call('AudioPlayback','GetVolume',{})['result']
            c.call('AudioPlayback','SetVolume',{'Volume':0})
            try:
                c.call('SystemCore','StartApp',{'AppId':app['app_id']})
                c.goodbye();c.serial.timeout=.2
                until=time.monotonic()+36
                while time.monotonic()<until:
                    raw.extend(c.serial.read(max(1,c.serial.in_waiting)))
                (ROOT/'runtime/learning-page-test.log').write_bytes(raw)
                assert all(('LEARNING_PAGE_OK:'+str(i)).encode() in raw for i in range(1,9)),'Some pages did not complete'
                assert not any(s in raw for s in (b'assert failed:',b'Guru Meditation',b'Rebooting...',b'ESP-ROM:')),'Device restarted during card rendering'
                c.serial.timeout=25;c.hello()
                active=c.call('SystemCore','GetActiveApp',{})['result']
                assert active['app_id']==app['app_id'] and active['state']=='Running' and not active['last_error'],active
                passed=True
            finally:
                if not c.session_active:c.hello()
                c.call('AudioPlayback','SetVolume',{'Volume':volume})
    finally:
        install_app(args.port,release)
        with StoryClient(args.port,timeout=25) as c:
            c.hello()
            app=next(a for a in c.call('SystemCore','ListApps',{})['result'] if a['manifest']['id']=='local.lightlearning')
            c.call('SystemCore','StartApp',{'AppId':app['app_id']})
    report={'passed':passed,'cards_rendered':6,'arithmetic_opened':True,'english_opened':True,'release_app_restored':True}
    (ROOT/'runtime/learning-page-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
