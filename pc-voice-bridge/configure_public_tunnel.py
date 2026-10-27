"""Select a managed public entry without changing cloud credentials or pairing keys."""
import argparse,importlib.util
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--target',type=Path,required=True)
parser.add_argument('--provider',choices=['localhost-run','cloudflare'],default='localhost-run')
args=parser.parse_args();root=args.target.resolve();module_path=root/'scripts/config_store.py'
if not module_path.is_file():raise SystemExit('Deploy the speech bridge sources first')
spec=importlib.util.spec_from_file_location('standalone_speech_config',module_path)
config_store=importlib.util.module_from_spec(spec);spec.loader.exec_module(config_store)
config_store.ROOT=root;config_store.CONFIG=root/'config/assistant.json'
config=config_store.load();config['network_mode']='ssh_tunnel' if args.provider=='localhost-run' else 'quick_tunnel'
config_store.save(config)
print('Public provider selected. Restart the workbench, then pair over USB if its address changes.')
