"""Update a device's public speech endpoint over USB without reinstalling apps."""
import argparse, sys, time
from pathlib import Path
from deploy_audiobook_sleep import StoryClient

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--model-root', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.model_root.resolve() / 'scripts'))
    import config_store
    config = config_store.load()
    url, token = config.get('device_url', ''), config.get('device_token', '')
    if not url.startswith('wss://') or not token:
        raise SystemExit('Start the public speech gateway before pairing')
    with StoryClient(args.port, timeout=25) as client:
        client.hello()
        def call(service, function, arguments=None):
            return client.call(service, function, arguments or {})['result']
        if call('Wifi', 'GetGeneralState') != 'Connected':
            raise SystemExit('Connect the device to Wi-Fi before pairing')
        call('LocalVoice', 'Disconnect')
        deadline = time.monotonic() + 15
        while call('LocalVoice', 'GetState')['active']:
            if time.monotonic() > deadline:
                raise TimeoutError('Assistant did not release audio')
            time.sleep(.2)
        call('LocalVoice', 'SetConnection', {'Url': url, 'Token': token})
        call('LocalVoice', 'Connect')
        deadline = time.monotonic() + 100
        while True:
            state = call('LocalVoice', 'GetState')
            if state['channel']:
                break
            if state['state'] == 'Error':
                raise RuntimeError(state['message'])
            if time.monotonic() > deadline:
                raise TimeoutError('Public connection timed out')
            time.sleep(.4)
    config = config_store.load()
    config['device_address_changed'] = False
    config_store.save(config)
    print('Device paired over public WSS; apps and cloud credentials unchanged.')

if __name__ == '__main__':
    main()
