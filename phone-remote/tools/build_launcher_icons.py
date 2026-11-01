"""Export the selected original warm-pony illustration for Android launchers."""
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
source=Image.open(ROOT/'assets/warm-pony-source.png').convert('RGB')
res=ROOT/'android/res'
for density,size in [('mdpi',48),('hdpi',72),('xhdpi',96),('xxhdpi',144),('xxxhdpi',192)]:
    target=res/('mipmap-'+density);target.mkdir(parents=True,exist_ok=True)
    source.resize((size,size),Image.Resampling.LANCZOS).save(target/'ic_launcher.png')
# Android's adaptive layer is 108dp. Keep the artwork in the central 72dp
# instead of letting a circular launcher mask cut through the pony's ears.
foreground=Image.new('RGB',(432,432),(255,217,164))
foreground.paste(source.resize((288,288),Image.Resampling.LANCZOS),(72,72))
target=res/'drawable-xxxhdpi';target.mkdir(parents=True,exist_ok=True)
foreground.save(target/'ic_launcher_foreground.png')
target=res/'values';target.mkdir(parents=True,exist_ok=True)
(target/'launcher_colors.xml').write_text('<resources><color name="launcher_background">#FFD9A4</color></resources>\n',encoding='utf-8')
target=res/'mipmap-anydpi-v26';target.mkdir(parents=True,exist_ok=True)
xml='<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android"><background android:drawable="@color/launcher_background"/><foreground android:drawable="@drawable/ic_launcher_foreground"/></adaptive-icon>\n'
for name in ('ic_launcher','ic_launcher_round'):(target/(name+'.xml')).write_text(xml,encoding='utf-8')
print('Warm pony Android icon resources exported')
