"""Reproduce the shared OFL title supplement from the pinned Noto source."""
import argparse
import hashlib
import json
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT=Path(__file__).resolve().parents[3]

def main():
    p=argparse.ArgumentParser();p.add_argument('--font',type=Path,required=True);a=p.parse_args()
    metadata=json.loads((ROOT/'samples/songs/font-source-20261104.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(a.font.read_bytes()).hexdigest()==metadata['source_sha256']
    font=TTFont(a.font,recalcTimestamp=False)
    font=instantiateVariableFont(font,{'wght':metadata['weight']},inplace=True)
    options=subset.Options();options.name_IDs=['*'];options.name_legacy=True;options.name_languages=['*']
    sub=subset.Subsetter(options=options);sub.populate(text=metadata['characters']);sub.subset(font)
    names={1:'Story Title Supplement',2:'Regular',3:'StoryTitleSupplement-Regular',4:'Story Title Supplement Regular',6:'StoryTitleSupplement-Regular',16:'Story Title Supplement',17:'Regular'}
    for record in font['name'].names:
        if record.nameID in names:record.string=names[record.nameID].encode(record.getEncoding())
    output=ROOT/'platform/super_s3_216/littlefs/system/fonts/audiobook-title-extra.ttf'
    font.save(output)
    assert hashlib.sha256(output.read_bytes()).hexdigest()==metadata['output_sha256']
    print('Verified title supplement: '+metadata['characters'])

if __name__=='__main__':main()
