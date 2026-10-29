"""Build an OFL font subset for the Chinese theme chooser."""
import argparse,hashlib,json
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/NotoSansSC-VF.ttf'));a=p.parse_args()
    text='桌面主题经典Q版赛博朋克'
    font=TTFont(a.font,recalcTimestamp=False);assert font['name'].getDebugName(1)=='Noto Sans SC'
    font=instantiateVariableFont(font,{'wght':400},inplace=True)
    options=subset.Options();options.name_IDs=['*'];sub=subset.Subsetter(options=options);sub.populate(text=text);sub.subset(font)
    for record in font['name'].names:
        value={1:'Desktop Theme Supplement',2:'Regular',3:'DesktopThemeSupplement-Regular',4:'Desktop Theme Supplement Regular',6:'DesktopThemeSupplement-Regular',16:'Desktop Theme Supplement',17:'Regular'}.get(record.nameID)
        if value:record.string=value.encode(record.getEncoding())
    assert all(ord(c) in font.getBestCmap() for c in text)
    out=ROOT/'platform/super_s3_216/littlefs/system/fonts/desktop-theme-extra.ttf';font.save(out)
    index=out.parent/'index.json';doc=json.loads(index.read_text(encoding='utf-8'));doc['fonts']=[f for f in doc['fonts'] if f['id']!='desktop_theme']
    doc['fonts'].append({'id':'desktop_theme','kind':'file','src':out.name,'languages':['en','zh_CN'],'fallbacks':['${font.zh_CN}']})
    index.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    info={'family':'Noto Sans SC','source_sha256':hashlib.sha256(a.font.read_bytes()).hexdigest(),'characters':text,'license':'SIL Open Font License 1.1','output_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
    (ROOT/'themes/cyberpunk-v1/font-source.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Theme picker font:',out.stat().st_size,'bytes; all characters checked')
if __name__=='__main__':main()
