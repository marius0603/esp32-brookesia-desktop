"""Install ESP-IDF 6.0.2 beside the existing toolchain, without changing system PATH."""
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile
from prepare_idf_metadata import prepare

ROOT = Path(__file__).resolve().parents[1]
(ROOT / 'runtime').mkdir(exist_ok=True)
IDF = ROOT.parent / 'esp-idf-v6.0.2'
archive = ROOT / 'tools/cache/esp-idf-v6.0.2.zip'
url = 'https://dl.espressif.com/github_assets/espressif/esp-idf/releases/download/v6.0.2/esp-idf-v6.0.2.zip'
if not (IDF / 'tools/idf_tools.py').exists():
    if not archive.exists():
        partial = archive.with_suffix('.zip.partial')
        with urllib.request.urlopen(url, timeout=60) as response, partial.open('wb') as output:
            total = int(response.headers.get('Content-Length', '0'))
            downloaded = 0
            last = -1
            while chunk := response.read(4 * 1024 * 1024):
                output.write(chunk)
                downloaded += len(chunk)
                percent = downloaded * 100 // total if total else downloaded // (50 * 1024 * 1024)
                if percent // 5 != last:
                    last = percent // 5
                    (ROOT / 'runtime/idf6-download.json').write_text(json.dumps({'bytes': downloaded, 'total': total, 'percent': percent}), encoding='utf-8')
                    print(f'ESP-IDF source download {percent}%', flush=True)
        partial.replace(archive)
    with zipfile.ZipFile(archive) as source:
        base = ROOT.parent.resolve()
        if not all((base / name).resolve().is_relative_to(base) for name in source.namelist()):
            raise SystemExit('Unsafe archive path')
        print('Extracting ESP-IDF 6.0.2...', flush=True)
        source.extractall(base)
prepare(IDF)
env = os.environ.copy()
env['IDF_TOOLS_PATH'] = str(ROOT.parent / 'i6')
env['IDF_GITHUB_ASSETS'] = 'dl.espressif.com/github_assets'
base_python = str(Path(sys.base_prefix) / 'python.exe')
subprocess.run([base_python, str(IDF / 'tools/idf_tools.py'), 'install', '--targets=esp32s3'], env=env, check=True)
subprocess.run([base_python, str(IDF / 'tools/idf_tools.py'), 'install-python-env'], env=env, check=True)
print('ESP-IDF 6.0.2 ready', flush=True)
