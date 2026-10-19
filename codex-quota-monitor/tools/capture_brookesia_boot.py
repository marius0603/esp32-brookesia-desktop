"""Capture console output without resetting a just-flashed device."""
import argparse
from pathlib import Path
import time
import serial

parser = argparse.ArgumentParser()
parser.add_argument('--port', default='COM5')
parser.add_argument('--seconds', type=float, default=45)
parser.add_argument('--reset', action='store_true', help='Reset through esptool and capture from the same open port')
args = parser.parse_args()
if args.reset:
    import esptool
    esp = esptool.detect_chip(args.port, baud=115200)
    mac = ':'.join(f'{byte:02x}' for byte in esp.read_mac())
    if esp.CHIP_NAME != 'ESP32-S3' or mac != '44:bd:8d:78:9f:d8':
        esp._port.close()
        raise SystemExit('Unexpected device')
    esp.hard_reset()
    port = esp._port
    port.timeout = 0.5
else:
    port = serial.Serial(port=None, baudrate=115200, timeout=0.5)
    port.dtr = False
    port.rts = False
    port.port = args.port
    deadline = time.monotonic() + 20
    while True:
        try:
            port.open()
            break
        except serial.SerialException:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)
output = Path(__file__).resolve().parents[1] / 'runtime/brookesia-device-boot.log'
deadline = time.monotonic() + args.seconds
try:
    with output.open('wb') as log:
        while time.monotonic() < deadline:
            data = port.read(max(1, port.in_waiting))
            if data:
                log.write(data)
                log.flush()
finally:
    port.close()
print(output)
print(output.read_bytes().decode('utf-8', errors='replace')[-9000:])
