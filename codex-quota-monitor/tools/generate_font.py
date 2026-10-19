"""Generate a small Chinese LVGL font from this computer's local font file."""
import os
from pathlib import Path
import re
import subprocess
from runtime_paths import find_node

root = Path(__file__).resolve().parents[1]
text = (root / "firmware/main/quota_ui.c").read_text(encoding="utf-8")
app_source = root / "brookesia/components/codex_quota_app/codex_quota_app.cpp"
if app_source.exists():
    text += app_source.read_text(encoding="utf-8")
symbols = "".join(sorted(set(re.findall(r"[\u3000-\u9fff\uff00-\uffef]", text))))
node = find_node()
font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/simhei.ttf"
converter = root / "tools/font-converter/node_modules/lv_font_conv/lv_font_conv.js"
subprocess.run([
    str(node), str(converter), "--font", str(font), "--size", "20", "--bpp", "4",
    "--format", "lvgl", "--lv-include", "lvgl.h", "--no-compress", "--range", "0x20-0x7e", "--symbols", symbols,
    "--lv-font-name", "quota_font", "--output", str(root / "firmware/main/quota_font.c"),
], check=True)
output = root / "firmware/main/quota_font.c"
output.write_text(output.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8", newline="\n")
if app_source.exists():
    (app_source.parent / "codex_quota_font.c").write_text(
        output.read_text(encoding="utf-8").replace("quota_font", "codex_quota_font"),
        encoding="utf-8", newline="\n",
    )
print(f"Generated quota_font.c with {len(symbols)} Chinese glyphs")
