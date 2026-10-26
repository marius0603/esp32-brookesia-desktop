"""Add the missing story-title glyph using an OFL Noto Sans SC variable font.

Requires fonttools; e.g. --font C:/Windows/Fonts/NotoSansSC-VF.ttf.
The system Chinese font remains the fallback for all other characters.
"""
import argparse
import hashlib
import json
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

APP = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--font', type=Path, required=True)
args = parser.parse_args()
font = TTFont(args.font, recalcTimestamp=False)
names = {n.nameID: n.toUnicode() for n in font['name'].names}
assert names[1] == 'Noto Sans SC' and 'SIL Open Font License' in names[13]
font = instantiateVariableFont(font, {'wght': 400}, inplace=True)
options = subset.Options()
options.name_IDs = ['*']
options.name_legacy = True
options.name_languages = ['*']
subsetter = subset.Subsetter(options=options)
subsetter.populate(text='蝌')
subsetter.subset(font)
for record in font['name'].names:
    replacement = {1: 'Story Title Supplement', 2: 'Regular', 3: 'StoryTitleSupplement-Regular',
        4: 'Story Title Supplement Regular', 6: 'StoryTitleSupplement-Regular',
        16: 'Story Title Supplement', 17: 'Regular'}.get(record.nameID)
    if replacement:
        record.string = replacement.encode(record.getEncoding())
output = APP / 'src/res/fonts'
output.mkdir(parents=True, exist_ok=True)
font.save(output / 'story-title-extra.ttf')
system_fonts = APP.parents[1] / 'platform/super_s3_216/littlefs/system/fonts'
system_fonts.mkdir(parents=True, exist_ok=True)
(system_fonts / 'audiobook-title-extra.ttf').write_bytes((output / 'story-title-extra.ttf').read_bytes())
check = TTFont(output / 'story-title-extra.ttf')
assert ord('蝌') in check.getBestCmap() and 'fvar' not in check
license_text = (APP.parents[1] / 'licenses/notosanssc-OFL.txt').read_text(encoding='utf-8')
if names[0] not in license_text:
    license_text = names[0] + '\n\n' + license_text
(output / 'OFL.txt').write_text('\n'.join(line.rstrip() for line in license_text.splitlines()) + '\n', encoding='utf-8', newline='\n')
metadata = {'source_family': names[1], 'source_version': names[5],
    'source_sha256': hashlib.sha256(args.font.read_bytes()).hexdigest(),
    'license': 'SIL Open Font License 1.1', 'weight': 400, 'characters': '蝌',
    'fallback': '${font.zh_CN}'}
(output / 'source.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Generated story-title-extra.ttf:', (output / 'story-title-extra.ttf').stat().st_size, 'bytes')
