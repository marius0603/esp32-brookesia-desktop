"""Visual smoke check using controlled fixtures, not additional account queries."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quota_monitor.preview import show_preview
from PIL import Image, ImageDraw, ImageFont

snapshot = json.loads((ROOT / "runtime/latest.json").read_text(encoding="utf-8"))
snapshot.update(sampled_at=int(time.time()), status="ok")
cases = []
cases.append(("正常额度（模拟）", copy.deepcopy(snapshot)))
low = copy.deepcopy(snapshot)
low["windows"][0]["used"] = 95
cases.append(("低额度（模拟）", low))
stale = copy.deepcopy(snapshot)
stale["sampled_at"] -= 181
cases.append(("数据过期（模拟）", stale))
cases.append(("首次同步前（模拟）", {"status": "starting", "windows": [], "sampled_at": None}))

class Fixture:
    def __init__(self, data): self.data = data
    def get_snapshot(self): return self.data
    def request_refresh(self): pass

contact = Image.new("RGB", (960, 1040), "#101820")
painter = ImageDraw.Draw(contact)
font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
with tempfile.TemporaryDirectory(prefix="quota-preview-") as temp:
    for index, (name, packet) in enumerate(cases):
        path = Path(temp) / f"{index}.png"
        show_preview(Fixture(packet), export_path=path)
        x, y = (index % 2) * 480, (index // 2) * 520
        painter.text((x + 240, y + 20), name, anchor="mm", font=font, fill="#e2edf8")
        with Image.open(path) as frame:
            contact.paste(frame.resize((480, 480)), (x, y + 40))
contact.save(ROOT / "artifacts/state-preview.png")
print("Rendered normal / low / stale / missing-data scenarios.")
