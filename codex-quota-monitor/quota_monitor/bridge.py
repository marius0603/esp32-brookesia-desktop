"""Serial delivery, conservative auto-detection and firmware identity handshake."""
import json
import logging
import time
import serial
from serial.tools import list_ports
from .model import encode_frame

LOG = logging.getLogger(__name__)


class SerialBridge:
    def __init__(self, config, get_snapshot, request_refresh, set_device, stop):
        self.config, self.get_snapshot = config, get_snapshot
        self.request_refresh, self.set_device, self.stop = request_refresh, set_device, stop

    def candidates(self):
        configured = self.config.get("serial_port", "auto")
        if configured in ("off", "disabled", "none"):
            return []
        if configured != "auto":
            return [configured]
        # Never probe Bluetooth/other serial equipment automatically.
        return [p.device for p in list_ports.comports() if p.vid == 0x303A]

    def run(self):
        while not self.stop.is_set():
            for port in self.candidates():
                if self.stop.is_set():
                    break
                try:
                    self._connect(port)
                except (serial.SerialException, OSError, ValueError):
                    self.set_device("disconnected")
            self.stop.wait(3)

    def _connect(self, port):
        connection = serial.Serial(port=None, baudrate=self.config.get("baudrate", 115200), timeout=0.3, write_timeout=2)
        # Set control lines before opening, so auto-open never pulses a reset line.
        connection.dtr = False
        connection.rts = False
        connection.port = port
        with connection:
            verified = False
            deadline = time.monotonic() + 8
            next_send = 0
            buffer = bytearray()
            while not self.stop.is_set():
                chunk = connection.read(min(connection.in_waiting or 1, 512))
                buffer.extend(chunk)
                if len(buffer) > 4096:
                    buffer.clear()
                while b"\n" in buffer:
                    line, _, rest = buffer.partition(b"\n")
                    buffer = bytearray(rest)
                    try:
                        message = json.loads(line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if not isinstance(message, dict):
                        continue
                    if message.get("type") == "hello" and message.get("device") == "codex-quota-monitor" and message.get("v") == 1:
                        verified = True
                        self.set_device(port)
                    if verified and message.get("type") == "refresh":
                        self.request_refresh()
                if not verified:
                    if time.monotonic() > deadline:
                        return
                    continue
                if time.monotonic() >= next_send:
                    connection.write(encode_frame(self.get_snapshot()))
                    next_send = time.monotonic() + 2
