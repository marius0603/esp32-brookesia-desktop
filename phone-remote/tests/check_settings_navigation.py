"""Check event subscription, routing and resource registration agree."""
import argparse,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--upstream',type=Path,required=True);a=p.parse_args();app=a.upstream/'app/brookesia_app_settings'
 def actions(file):
  s=file.read_text(encoding='utf-8');body=re.search(r'NAVIGATION_ACTIONS\s*=\s*\{(.*?)\};',s,re.S).group(1)
  return [v.strip() for v in body.split(',') if v.strip()]
 assert actions(app/'src/settings_app.cpp')==actions(app/'src/private/settings_app_internal.hpp'),'Event subscription and navigation whitelist diverge'
 assert '"settings.open.bluetooth"' in actions(app/'src/settings_app.cpp')
 cpp=(app/'src/settings_app.cpp').read_text(encoding='utf-8');assert 'NavigationTarget{"settings.open.bluetooth", "bluetooth"}' in cpp
 source=ROOT/'packages/resources/bluetooth-settings-s3.34';root=json.loads((source/'root.json').read_text());flow=json.loads((source/'flows/content.json').read_text())
 assert 'screens/bluetooth.json' in root['assets'] and 'bluetooth' in flow['screens'];assert any(x['action']=='settings.open.bluetooth' and x['to']=='bluetooth' for x in flow['transitions'])
 print('Bluetooth navigation: both event tables, route target, root asset and flow registration agree.')
if __name__=='__main__':main()
