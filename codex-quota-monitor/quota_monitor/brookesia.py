"""Deliver cached quota through the standard Brookesia USB Storage service."""
import json
import re
import time
import serial
from brookesia_usb.cli import UsbClient
from .bridge import SerialBridge


class StableUsbClient(UsbClient):
    """Keep the pinned upstream protocol, but set control lines before opening."""
    def __init__(self, port, baudrate=115200, timeout=5):
        self.port = port
        self.serial = serial.Serial(port=None, baudrate=baudrate, timeout=timeout, write_timeout=timeout)
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.port = port
        self.serial.open()
        self.timeout = timeout
        self.request_id = 1
        self.session_active = False
        self._hello_request_pending = False
        self.diagnostic_lines = []

    def read_json(self):
        serial_timeout = self.serial.timeout
        budget = serial_timeout if isinstance(serial_timeout, (int, float)) else getattr(self, 'timeout', 5)
        deadline = time.monotonic() + budget
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('timed out waiting for device response')
            line = self.serial.readline()
            if not line:
                raise TimeoutError('timed out waiting for device response')
            # Console flushes can leave an empty CRLF after log suppression.
            if not line.strip():
                continue
            # QuickJS console.log bypasses ESP log suppression. This App emits
            # one known ACK per sample; keep it separate from protocol replies.
            if line.startswith(b'Codex quota UI updated: '):
                self.diagnostic_lines.append(line)
                continue
            # The app's low-rate renderer telemetry can be buffered just before
            # USB log suppression takes effect. Keep only this exact known form
            # separate; panics and unrelated malformed responses still fail.
            if re.fullmatch(rb'I \(\d+\) S3_PERF: render cycles=\d+ avg_us=\d+ max_us=\d+\r?\n', line):
                self.diagnostic_lines.append(line)
                continue
            try:
                value = json.loads(line.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                if not self.session_active:
                    continue
                raise RuntimeError(f'invalid device response: {line!r}') from exc
            if not isinstance(value, dict):
                if not self.session_active:
                    continue
                raise RuntimeError('device response is not an object')
            return value

    def wait_for(self, request_id, *operations):
        original_timeout = self.serial.timeout
        budget = original_timeout if isinstance(original_timeout, (int, float)) else self.timeout
        deadline = time.monotonic() + budget
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('timed out waiting for matching device response')
                self.serial.timeout = remaining
                response = self.read_json()
                if response.get('request_id') == request_id and response.get('op') in operations:
                    return response
        finally:
            self.serial.timeout = original_timeout

    def call(self, service, function, args):
        try:
            return super().call(service, function, args)
        except RuntimeError as exc:
            # The S3 USB transport may release a session during a transient
            # connection-state change around Flash I/O. This explicit rejection
            # means the function was not executed, so retrying it is safe.
            if str(exc) != 'invalid_command: hello is required first':
                raise
            self.session_active = False
            self.hello()
            return super().call(service, function, args)


class BrookesiaBridge(SerialBridge):
    def _connect(self, port):
        while not self.stop.is_set():
            try:
                with StableUsbClient(port, self.config.get('baudrate', 115200)) as client:
                    client.hello()
                    packet = self.get_snapshot()
                    packet['bridge_at'] = int(time.time())
                    response = client.call('Storage', 'FSWriteText', {
                        'Path': '/littlefs/quota.json',
                        'Data': json.dumps(packet, ensure_ascii=False, allow_nan=False),
                    })
                    # USB unwraps FunctionResult: void writes return result=null;
                    # failed service calls use ok=false and UsbClient raises.
                    if response.get('ok') is not True:
                        raise RuntimeError('quota_write_failed')
                self.set_device(port)
            except (RuntimeError, TimeoutError) as exc:
                raise serial.SerialException('Brookesia USB delivery failed') from exc
            if self.stop.wait(15):
                return
