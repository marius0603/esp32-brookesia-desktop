"""Explicitly retain the next device recording locally, or cancel that request."""
import argparse,os,sys
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--target',type=Path,required=True)
parser.add_argument('--cancel',action='store_true')
args=parser.parse_args();root=args.target.resolve()
if not (root/'config/assistant.json').is_file():raise SystemExit('Speech runtime configuration not found')
os.environ['QWEN_SPEECH_ROOT']=str(root);sys.path.insert(0,str(root/'scripts'))
import config_store
config=config_store.load();config['diagnostic_next_recording']=not args.cancel;config_store.save(config)
print('Diagnostic capture cancelled.' if args.cancel else 'Next submitted recording will be saved locally in outputs/diagnostics, then capture disables itself.')
