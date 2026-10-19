"""Build the quota App with its current manifest version."""
from pathlib import Path
import subprocess
import sys
root = Path(__file__).resolve().parents[1]
raise SystemExit(subprocess.call([sys.executable, str(root/'tools/build_brookesia_app.py'), str(root.parent/'brookesia-apps/codex-quota')]))
