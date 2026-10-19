"""Install a project-local ESP-IDF 5.5.5 toolchain without changing system PATH."""
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile
from prepare_idf_metadata import prepare

ROOT = Path(__file__).resolve().parents[1]
IDF = ROOT / "tools/esp-idf-v5.5.5"
BASE_PYTHON = Path(sys.base_prefix) / "python.exe"
environment = os.environ.copy()
environment["IDF_TOOLS_PATH"] = str(ROOT / "tools/idf-tools")
environment["IDF_GITHUB_ASSETS"] = "dl.espressif.com/github_assets"
if not (IDF / "tools/idf_tools.py").exists():
    cache = ROOT / "tools/cache"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / "esp-idf-v5.5.5.zip"
    if not archive.exists():
        print("Downloading the full ESP-IDF source archive (about 2 GB).", flush=True)
        urllib.request.urlretrieve(
            "https://dl.espressif.com/github_assets/espressif/esp-idf/releases/download/v5.5.5/esp-idf-v5.5.5.zip",
            archive,
        )
    with zipfile.ZipFile(archive) as zipped:
        destination = (ROOT / "tools").resolve()
        if not all((destination / name).resolve().is_relative_to(destination) for name in zipped.namelist()):
            raise SystemExit("Archive contains an invalid path")
        zipped.extractall(destination)
tool = str(IDF / "tools/idf_tools.py")
prepare(IDF)
subprocess.run([str(BASE_PYTHON), tool, "install", "--targets=esp32s3"], env=environment, check=True)
subprocess.run([str(BASE_PYTHON), tool, "install-python-env"], env=environment, check=True)
print("Toolchain installed. Run tools/build-firmware.ps1.")
