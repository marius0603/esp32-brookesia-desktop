"""Deploy bridge sources into an existing standalone Qwen installation."""
from pathlib import Path
import argparse,datetime,shutil

parser=argparse.ArgumentParser();parser.add_argument('--target',type=Path,required=True)
args=parser.parse_args();target=args.target.resolve();source=Path(__file__).resolve().parent
if target.is_relative_to(source.parent):raise SystemExit('Keep the standalone runtime outside the source repository')
if not (target/'envs/tts/Scripts/python.exe').is_file() or not (target/'models').is_dir():
    raise SystemExit('Install the Qwen models and environments first')
backup=target/'logs'/('bridge-source-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(parents=True)
modules=['config_store.py','deepseek_client.py','engines.py','engine_worker.py','conversation.py','device_gateway.py','public_tunnel.py','web_extension.py','assistant.html']
for name in modules:
    destination=target/'scripts'/name
    if destination.exists():shutil.copy2(destination,backup/name)
    shutil.copy2(source/name,destination)
for file in (source/'workbench').iterdir():
    destination=target/'scripts'/file.name if file.suffix in ('.py','.html') else target/file.name
    if destination.exists():shutil.copy2(destination,backup/file.name)
    shutil.copy2(file,destination)
print('Bridge deployed. Private configuration, models and outputs preserved.')
print('Restart with Stop.ps1 then Start.ps1 in',target)
