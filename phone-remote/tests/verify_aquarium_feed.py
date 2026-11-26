"""Verify the aquarium feed command over the real paired BLE link."""
import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from bleak import BleakClient, BleakScanner

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'codex-quota-monitor/tools'))
from maintenance_client import SharedPowerDiagnosticClient

SESSION = '1775ff51-6b43-439b-877c-060f2d9bed07'
REMOTE = '1775ff55-6b43-439b-877c-060f2d9bed07'


async def verify(port, tools, classes):
    with SharedPowerDiagnosticClient(port, timeout=15) as usb:
        usb.hello()

        def call(service, function, **args):
            return usb.call_timeout(service, function, args, 16000)['result']

        async def wait(read, predicate, seconds=22):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                value = read()
                if predicate(value):
                    return value
                await asyncio.sleep(.2)
            raise TimeoutError(value)

        boot = call('DeviceModes', 'GetState')
        assert boot['firmware_version'] == '0.8.3-s3.96' and not boot['screen_locked']
        assert not call('PhoneProvisioning', 'GetState')['active'], 'Close the current Bluetooth session first'
        def catalog():
            return {row['manifest']['id']: row for row in call('SystemCore', 'ListApps')}

        apps = await wait(catalog, lambda value: 'local.aquarium' in value)
        app = apps['local.aquarium']['app_id']
        home = apps['brookesia.system.super.shell']['app_id']
        active = lambda: call('SystemCore', 'GetActiveApp')
        profile = lambda: call('DeviceModes', 'AquariumProfile')
        call('DeviceModes', 'Wake')
        if active().get('app_id') == app:
            call('SystemCore', 'RequestCloseApp', AppId=app)
        await wait(active, lambda value: value.get('app_id') in (None, home))
        call('PhoneProvisioning', 'StartRemote')
        java = None
        try:
            setup = await wait(lambda: call('PhoneProvisioning', 'GetSetup'), lambda value: value['active'])
            env = os.environ.copy()
            env['XIAOMA_TEST_POP'] = setup['pop']
            java = subprocess.Popen(
                [tools['java'], '-cp', str(classes) + os.pathsep + tools['bc'], 'com.xiaoma.remote.ProtocolHarness'],
                env=env, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            )

            def protocol(operation, data=None):
                arg = ' ' + base64.b64encode(data).decode() if data is not None else ''
                java.stdin.write(operation + arg + '\n')
                java.stdin.flush()
                value = java.stdout.readline().strip()
                if value == 'OK':
                    return value
                if not value:
                    raise RuntimeError('Protocol harness produced no response')
                return base64.b64decode(value)

            device = await BleakScanner.find_device_by_filter(
                lambda _, advertising: advertising.local_name == setup['device_name'], timeout=20
            )
            if device is None:
                raise TimeoutError('The board did not advertise the paired remote service')
            async with BleakClient(device, timeout=20) as client:
                async def exchange(endpoint, payload):
                    await client.write_gatt_char(endpoint, payload, response=True)
                    return bytes(await client.read_gatt_char(endpoint))

                proof = await exchange(SESSION, protocol('hello'))
                result = await exchange(SESSION, protocol('prove', proof))
                assert protocol('verify', result) == 'OK'

                async def command(cmd, **fields):
                    payload = json.dumps(dict(cmd=cmd, **fields)).encode()
                    raw = await exchange(REMOTE, protocol('crypt', payload))
                    return json.loads(protocol('crypt', raw))

                info = await command('status')
                assert info['ok'] and info['aquarium_feed_rssi'] == -25
                closed = await command('aquarium_feed', rssi=-25)
                assert not closed['ok'] and '打开口袋鱼缸' in closed['error']
                call('SystemCore', 'StartApp', AppId=app)
                before = await wait(profile, lambda value: value.get('active') and value.get('grass_active'))
                rejected = [await command('aquarium_feed', rssi=v) for v in (-26, -27, -37, 0, -25.5)]
                rejected.append(await command('aquarium_feed'))
                assert all(not row['ok'] and '靠近' in row['error'] for row in rejected)
                assert profile()['feed_count'] == before['feed_count']
                start = await command('aquarium_feed', rssi=-25)
                assert start['ok'], start
                showing = await wait(profile, lambda value: value.get('food_visible') and
                                     value['feed_count'] == before['feed_count'] + 1, 3)
                duplicate = await command('aquarium_feed', rssi=-23)
                assert not duplicate['ok'] and '刚投喂过' in duplicate['error'], duplicate
                gone = await wait(profile, lambda value: value.get('food_visible') is False, 6)
                assert gone['feed_count'] == showing['feed_count'] and gone['frames'] > showing['frames']
                assert (await command('status'))['ok']
                after = call('DeviceModes', 'GetState')
                assert after['uptime_ms'] > boot['uptime_ms'] and after['reset_reason'] == boot['reset_reason']
                print('Encrypted BLE: background, weak and malformed values rejected; threshold accepted once; pellets animated and cleared.')
        finally:
            if java:
                java.terminate()
                java.wait(timeout=5)
            call('PhoneProvisioning', 'Stop')
        assert active().get('app_id') == app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--tools', type=Path, required=True)
    parser.add_argument('--classes', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(verify(args.port, json.loads(args.tools.read_text(encoding='utf-8')), args.classes))


if __name__ == '__main__':
    main()
