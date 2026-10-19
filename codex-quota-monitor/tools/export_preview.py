from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from quota_monitor.preview import show_preview

(root / "artifacts").mkdir(exist_ok=True)
show_preview(export_path=root / "artifacts/desktop-preview.png")
print(root / "artifacts/desktop-preview.png")
