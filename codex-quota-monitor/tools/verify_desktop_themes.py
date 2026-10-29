"""Verify the installed theme switch, native rendering and preserved user data."""
import argparse,json,time
from pathlib import Path
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--expect-saved',type=int,choices=(0,1));a=p.parse_args()
    report={'passed':False,'switches':[]}
    with StoryClient(a.port,timeout=30) as c:
        original=c.serial.readline
        def readline(*args,**kwargs):
            data=original(*args,**kwargs)
            with (ROOT/'runtime/desktop-theme-usb.log').open('ab') as log:log.write(data)
            return data
        c.serial.readline=readline;c.hello()
        def f(s,n,args=None):return c.call(s,n,args or {})['result']
        deadline=time.monotonic()+80
        while True:
            apps=f('SystemCore','ListApps');state=f('DeviceModes','GetState')
            if any(app['app_id']==1 and app['state']=='Running' for app in apps) and state['desktop_theme_applied']>=0:break
            assert time.monotonic()<deadline,{'apps':apps,'state':state}
            time.sleep(1)
        assert state['firmware_version']=='0.8.3-s3.31' and state['cyber_theme_available'],state
        f('DeviceModes','Wake')
        if a.expect_saved is not None:assert state['desktop_theme_index']==state['desktop_theme_saved_index']==state['desktop_theme_applied']==a.expect_saved
        def selected(index):
            end=time.monotonic()+12
            while time.monotonic()<end:
                state=f('DeviceModes','GetState')
                if state['desktop_theme_index']==state['desktop_theme_applied']==index and not state['pending_save']:return state
                time.sleep(.2)
            raise AssertionError('Theme did not finish applying: '+str(state))
        for index in (0,1,0,1):
            f('DeviceModes','SetDesktopTheme',{'Index':index});state=selected(index)
            timing=f('DeviceModes','ProfileRefresh',{'Force':True})
            report['switches'].append({'index':index,'refresh':timing})
        for index in (-1,2,1.5):
            try:f('DeviceModes','SetDesktopTheme',{'Index':index})
            except RuntimeError:pass
            else:raise AssertionError('Invalid desktop theme was accepted')
        selected(1)
        latest=json.loads((ROOT/'runtime/desktop-theme-latest.json').read_text(encoding='utf-8'))
        before=json.loads((Path(latest['folder'])/'preservation.json').read_text(encoding='utf-8'))
        assert f('Audiobook','List')['tracks']==before['tracks']
        assert f('AudioPlayback','GetVolume')==before['volume']
        for path in ('/littlefs/audiobook-bookmark.json','/littlefs/audiobook-play-mode.json'):
            if before[path] is not None:assert f('Storage','FSReadText',{'Path':path})==before[path]
        settings=json.loads(f('Storage','FSReadText',{'Path':'/littlefs/apps/brookesia.general.settings/res/screens/display.json'}))
        card=next(n for n in settings['children'][0]['children'] if n['id']=='desktop_theme_card')
        choice=card['slots']['content'][1];assert choice['dropdownProps']['options']==['经典Q版','赛博朋克']
        fonts=json.loads(f('Storage','FSReadText',{'Path':'/littlefs/system/fonts/index.json'}));assert any(n['id']=='desktop_theme' for n in fonts['fonts'])
        images=json.loads(f('Storage','FSReadText',{'Path':'/littlefs/system/super/shell/images/index.json'}));assert sum(i['id'].startswith('cyber.') for i in images['images'])==11
        report.update(passed=True,stories=len(before['tracks']),volume=before['volume'],theme=state['desktop_theme_index'],saved_before=a.expect_saved)
    (ROOT/'runtime/desktop-theme-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
if __name__=='__main__':main()
