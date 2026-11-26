"""Build the Chinese aquarium glyph supplement from the OFL Noto Sans SC font."""
import argparse
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

APP = Path(__file__).resolve().parents[1]
FONTS = APP.parents[1] / "platform/super_s3_216/littlefs/system/fonts"
FONT = FONTS / "aquarium-extra.ttf"
FAMILY = "Aquarium Glyph Supplement"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True)
    args = parser.parse_args()
    text = "".join((APP / path).read_text(encoding="utf-8") for path in
                   ("src/app/main.js", "src/res/screens/main.json"))
    with TTFont(FONTS / "NotoSansSC-Regular.subset.ttf") as base:
        missing = {ord(char) for char in text if ord(char) >= 32} - base.getBestCmap().keys()
    with TTFont(args.font, recalcTimestamp=False) as font:
        assert font["name"].getDebugName(1) == "Noto Sans SC"
        assert missing and missing <= font.getBestCmap().keys()
        instantiateVariableFont(font, {"wght": 400}, inplace=True)
        options = subset.Options()
        options.name_IDs = ["*"]
        sub = subset.Subsetter(options=options)
        sub.populate(unicodes=missing)
        sub.subset(font)
        postscript_name = "AquariumGlyphSupplement-Regular"
        replacements = {1: FAMILY, 2: "Regular", 3: postscript_name, 4: FAMILY + " Regular",
                        6: postscript_name, 16: FAMILY, 17: "Regular"}
        for name in font["name"].names:
            if name.nameID in replacements:
                name.string = replacements[name.nameID].encode(name.getEncoding())
        assert set(font.getBestCmap()) == missing
        font.save(FONT)
    print(f"{FONT.name} covers {''.join(map(chr, sorted(missing)))} ({FONT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
