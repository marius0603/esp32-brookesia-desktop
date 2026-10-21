"""Check launcher icon discovery before opening any weather UI."""
import argparse
import json
from pathlib import Path
from verify_child_mode import Client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--require-weather-unopened', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    with Client(args.port, timeout=25) as client:
        client.hello()
        apps = client.call('SystemCore', 'ListApps', {})['result']
        visible = [app for app in apps if app['manifest']['visible']]
        for app in visible:
            manifest = app['manifest']
            assert manifest['icon_id'] and manifest['icon_path'], 'Missing launcher icon: ' + manifest['id']
        weather = next(app for app in apps if app['manifest']['id'] == 'local.weather')
        if args.require_weather_unopened:
            assert weather['state'] == 'Installed', 'Weather was already opened; this is not a cold-start check'
        resources = client.call('SdResources', 'GetState', {})['result']
        assert all(item['exists'] for item in resources['files'])
        child = client.call('ChildMode', 'GetState', {})['result']
        report = {'icons': [{'id': app['manifest']['id'], 'path': app['manifest']['icon_path'],
                             'state': app['state']} for app in visible],
                  'weather_unopened': weather['state'] == 'Installed',
                  'resources': resources, 'parent_pin_configured': child['configured']}
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'visible_icons': len(visible), 'weather_icon_path': weather['manifest']['icon_path'],
                      'weather_unopened': report['weather_unopened'],
                      'sd_resolutions': resources['sd_resolutions'],
                      'flash_resolutions': resources['flash_resolutions']}))


if __name__ == '__main__':
    main()
