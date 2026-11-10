import copy
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading
import time
from .bridge import SerialBridge
from .model import normalize
from .rpc import CodexClient
from .desktop import is_codex_running

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)


def load_config(path=None):
    config = json.loads(Path(path or ROOT / "config.json").read_text(encoding="utf-8-sig"))
    if not 15 <= config.get("poll_seconds", 60) <= 3600:
        raise ValueError("poll_seconds must be between 15 and 3600")
    if config.get("stale_seconds", 180) < config.get("poll_seconds", 60) * 2:
        raise ValueError("stale_seconds must be at least two poll intervals")
    if not 0 <= config.get("critical_percent", 10) < config.get("warning_percent", 20) <= 100:
        raise ValueError("invalid warning thresholds")
    return config


def setup_logging():
    (ROOT / "runtime").mkdir(exist_ok=True)
    handler = RotatingFileHandler(ROOT / "runtime/monitor.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")


class Monitor:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.refresh = threading.Event()
        self.last_attempt = 0.0
        self.pending_request = None
        self.request_only = config.get('device_protocol') == 'brookesia'
        self.snapshot = {
            "type": "quota", "v": 1, "sampled_at": None, "status": "starting",
            "windows": [], "plan": "", "bucket": "codex",
        }
        self.device = "disconnected"
        self.client = None
        self.threads = []

    def get_snapshot(self):
        with self.lock:
            return {
                **copy.deepcopy(self.snapshot), "device": self.device,
                "stale_after": self.config.get("stale_seconds", 180),
                "warning": self.config.get("warning_percent", 20),
                "critical": self.config.get("critical_percent", 10),
            }

    def persist(self):
        folder = ROOT / "runtime"
        folder.mkdir(exist_ok=True)
        with self.lock:
            packet = self.get_snapshot()
            packet["bridge_at"] = int(time.time())
            temporary = folder / "latest.json.tmp"
            temporary.write_text(json.dumps(packet, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            temporary.replace(folder / "latest.json")

    def set_device(self, device):
        with self.lock:
            if device != self.device:
                self.device = device
                self.persist()
                LOG.info("Display connection: %s", device)

    def request_refresh(self, request_id=None):
        if self.request_only:
            if not isinstance(request_id, str) or not 1 <= len(request_id) <= 120:
                return
            with self.lock:
                self.pending_request = request_id
                self.refresh.set()
            return
        # Shared throttle applies to both button and touch requests.
        if time.monotonic() - self.last_attempt >= 15:
            self.refresh.set()

    def poll_once(self, request_id=None):
        if self.request_only and (not request_id or not is_codex_running()):
            LOG.info('Quota query skipped: device request and running Codex desktop are required')
            return False
        self.last_attempt = time.monotonic()
        try:
            if self.client is None:
                self.client = CodexClient(self.config.get("codex_path", ""))
            result = self.client.read_quota()
            if self.request_only and (self.stop.is_set() or not is_codex_running()):
                return False
            packet = normalize(result)
            if request_id:
                packet['request_id'] = request_id
            with self.lock:
                self.snapshot = packet
            LOG.info("Quota updated: %s", ", ".join(f"{w['minutes']}min {100-w['used']:g}% remaining" for w in packet["windows"]))
            success = True
        except Exception as exc:
            error = str(exc) if str(exc) in ("auth_required", "quota_unavailable", "codex_not_found") else type(exc).__name__
            with self.lock:
                self.snapshot["status"] = "auth_required" if error == "auth_required" else "error"
                self.snapshot["error"] = error
                if request_id:
                    self.snapshot['request_id'] = request_id
            LOG.warning("Quota read failed: %s", error)
            if self.client:
                self.client.close()
                self.client = None
            success = False
        finally:
            # The desktop app must already exist. Its separate read-only query
            # helper is short-lived and never keeps the listener alive itself.
            if self.request_only and self.client:
                self.client.close()
                self.client = None
        self.persist()
        return success

    def _poll_loop(self):
        next_poll = 0
        while not self.stop.is_set():
            request = ROOT / "runtime/stop.request"
            if request.exists():
                request.unlink(missing_ok=True)
                self.stop.set()
                break
            if self.request_only and not is_codex_running():
                LOG.info('Codex desktop exited; stopping USB request listener')
                self.stop.set()
                break
            if (not self.request_only and time.monotonic() >= next_poll) or self.refresh.is_set():
                with self.lock:
                    request_id = self.pending_request
                    self.pending_request = None
                    self.refresh.clear()
                self.poll_once(request_id)
                next_poll = time.monotonic() + self.config.get("poll_seconds", 60)
            # File heartbeat lets an independently opened preview detect a stopped bridge.
            self.persist()
            if self.stop.wait(1):
                break
        if self.client:
            self.client.close()
            self.client = None

    def start(self):
        bridge_type = SerialBridge
        if self.config.get('device_protocol') == 'brookesia':
            from .brookesia import BrookesiaBridge
            bridge_type = BrookesiaBridge
        bridge = bridge_type(self.config, self.get_snapshot, self.request_refresh, self.set_device, self.stop)
        targets = [self._poll_loop, bridge.run]
        if self.request_only:
            targets.append(self._lifecycle_loop)
        for target in targets:
            thread = threading.Thread(target=target, daemon=True)
            self.threads.append(thread)
            thread.start()

    def _lifecycle_loop(self):
        # Separate from a potentially blocked cloud request so closing Codex
        # also interrupts its short-lived query helper promptly.
        while not self.stop.wait(1):
            if not is_codex_running():
                LOG.info('Codex desktop exited; stopping USB request listener')
                self.stop.set()
                break

    def close(self):
        self.stop.set()
        # Termination unblocks a pending RPC read before process shutdown.
        client = self.client
        if client and client.process.poll() is None:
            client.process.terminate()
        for thread in self.threads:
            thread.join(timeout=6)
