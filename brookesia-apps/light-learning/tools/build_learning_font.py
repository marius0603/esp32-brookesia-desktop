"""Build the OFL pinyin supplement from a Noto Sans SC variable TTF."""
import argparse,hashlib,json
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser()
parser.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/NotoSansSC-VF.ttf'))
args=parser.parse_args()
characters='āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü−'
font=TTFont(args.font,recalcTimestamp=False)
assert font['name'].getDebugName(1)=='Noto Sans SC'
font=instantiateVariableFont(font,{'wght':400},inplace=True)
options=subset.Options();options.name_IDs=['*']
subsetter=subset.Subsetter(options=options);subsetter.populate(text=characters);subsetter.subset(font)
for record in font['name'].names:
    replacement={1:'Learning Supplement',2:'Regular',3:'LearningSupplement-Regular',4:'Learning Supplement Regular',6:'LearningSupplement-Regular',16:'Learning Supplement',17:'Regular'}.get(record.nameID)
    if replacement:record.string=replacement.encode(record.getEncoding())
output=ROOT/'platform/super_s3_216/littlefs/system/fonts/learning-extra.ttf'
font.save(output)
metadata={'source_family':'Noto Sans SC','source_sha256':hashlib.sha256(args.font.read_bytes()).hexdigest(),'characters':characters,'license':'SIL Open Font License 1.1','fallback':'${font.zh_CN}'}
(ROOT/'brookesia-apps/light-learning/packs/font-source.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(output,output.stat().st_size)
