"""Run idf.py in the isolated ESP-Brookesia 0.8 / ESP-IDF 6.0.2 environment."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
IDF = ROOT.parent / 'esp-idf-v6.0.2'
PROJECT = ROOT.parent / 'esp-brookesia-v08/examples/system/super_s3_216'
env = os.environ.copy()
env.update(IDF_PATH=str(IDF), IDF_TOOLS_PATH=str(ROOT.parent/'i6'), IDF_TARGET='esp32s3',
           IDF_GITHUB_ASSETS='dl.espressif.com/github_assets', PYTHONIOENCODING='utf-8')
result = subprocess.run([sys.executable, str(IDF/'tools/idf_tools.py'), 'export', '--format', 'key-value'],
                        env=env, text=True, encoding='utf-8', capture_output=True, check=True)
for line in result.stdout.splitlines():
    if '=' in line:
        key,value=line.split('=',1)
        env[key]=value.replace('%PATH%',env['PATH'])
python=Path(env['IDF_PYTHON_ENV_PATH'])/'Scripts/python.exe'
raise SystemExit(subprocess.call([str(python),str(IDF/'tools/idf.py'),*sys.argv[1:]],env=env,cwd=PROJECT))
