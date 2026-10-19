import copy
import json
import queue
import threading
import unittest
from unittest.mock import patch
from quota_monitor.model import normalize, encode_frame, display_status, countdown
from quota_monitor.rpc import CodexClient, RpcError
from quota_monitor.service import Monitor
from quota_monitor.bridge import SerialBridge
from types import SimpleNamespace


def example():
    return {"rateLimitsByLimitId": {"codex": {
        "limitId": "codex", "planType": "plus",
        "primary": {"usedPercent": 25, "windowDurationMins": 300, "resetsAt": 2000},
        "secondary": {"usedPercent": 10, "windowDurationMins": 10080, "resetsAt": 9000},
    }}, "accountId": "private", "accessToken": "private"}


class ProtocolTests(unittest.TestCase):
    def test_multi_bucket_beats_legacy_view_and_omits_identity(self):
        data = example()
        data["rateLimits"] = {"primary": {"usedPercent": 99}}
        packet = normalize(data, 1000)
        self.assertEqual(packet["windows"][0]["used"], 25)
        self.assertNotIn("private", encode_frame(packet, 1001).decode())
        self.assertEqual(json.loads(encode_frame(packet, 1001))["sent_at"], 1001)

    def test_legacy_missing_second_window(self):
        bucket = example()["rateLimitsByLimitId"]["codex"]
        bucket["secondary"] = None
        self.assertEqual(len(normalize({"rateLimits": bucket})["windows"]), 1)

    def test_unknown_never_becomes_zero_or_full(self):
        for value in (None, "0", True, -1, 101, float("nan")):
            data = example()
            data["rateLimitsByLimitId"]["codex"]["primary"]["usedPercent"] = value
            self.assertEqual(len(normalize(data)["windows"]), 1)
        with self.assertRaises(ValueError):
            normalize({"rateLimits": {"primary": None, "secondary": None}})

    def test_reset_does_not_fabricate_new_allowance(self):
        packet = normalize(example(), 1000)
        self.assertEqual(countdown(2000, 2001), "等待同步")
        self.assertEqual(packet["windows"][0]["used"], 25)

    def test_stale_boundary_and_missing_timestamp(self):
        packet = {**normalize(example(), 1000), "stale_after": 180}
        self.assertEqual(display_status(packet, 1180), "ok")
        self.assertEqual(display_status(packet, 1181), "stale")
        self.assertEqual(display_status({"status": "auth_required", "sampled_at": None}), "auth_required")

    def test_failure_preserves_last_success_and_timestamp(self):
        monitor = Monitor({"stale_seconds": 180})
        client = unittest.mock.Mock()
        client.read_quota.side_effect = [example(), TimeoutError()]
        monitor.client = client
        with patch.object(monitor, "persist"):
            self.assertTrue(monitor.poll_once())
            original = copy.deepcopy(monitor.get_snapshot())
            self.assertFalse(monitor.poll_once())
        after = monitor.get_snapshot()
        self.assertEqual(after["sampled_at"], original["sampled_at"])
        self.assertEqual(after["windows"], original["windows"])
        self.assertEqual(after["status"], "error")

    def test_refresh_throttles_all_input_sources(self):
        monitor = Monitor({})
        with patch("quota_monitor.service.time.monotonic", return_value=100):
            monitor.last_attempt = 90
            monitor.request_refresh()
            self.assertFalse(monitor.refresh.is_set())
            monitor.last_attempt = 80
            monitor.request_refresh()
            self.assertTrue(monitor.refresh.is_set())

    def test_frame_size_limit(self):
        with self.assertRaises(ValueError):
            encode_frame({"padding": "x" * 3000})

    def test_unrelated_rpc_notifications_cannot_match_response(self):
        client = CodexClient.__new__(CodexClient)
        client.timeout, client.sequence, client.messages = 0.1, 0, queue.Queue()
        client._send = unittest.mock.Mock()
        client.messages.put({"method": "account/rateLimits/updated", "params": {}})
        client.messages.put({"id": 1, "result": {"correct": True}})
        self.assertEqual(client.call("account/rateLimits/read"), {"correct": True})

    def test_disconnect_and_rpc_error(self):
        for response in (None, {"id": 1, "error": {"code": 123, "message": "secret"}}):
            client = CodexClient.__new__(CodexClient)
            client.timeout, client.sequence, client.messages = 0.1, 0, queue.Queue()
            client._send = unittest.mock.Mock()
            client.messages.put(response)
            with self.assertRaises(RpcError) as context:
                client.call("account/rateLimits/read")
            self.assertNotIn("secret", str(context.exception))


class SerialTests(unittest.TestCase):
    def test_auto_detection_excludes_bluetooth_and_other_vendors(self):
        bridge = SerialBridge({}, None, None, None, threading.Event())
        ports = [SimpleNamespace(device="COM1", vid=None), SimpleNamespace(device="COM2", vid=0x303A), SimpleNamespace(device="COM3", vid=0x10C4)]
        with patch("quota_monitor.bridge.list_ports.comports", return_value=ports):
            self.assertEqual(bridge.candidates(), ["COM2"])

    def test_fragmented_hello_refresh_and_delivery(self):
        stop = threading.Event()
        connected, sent, refreshed = [], [], []
        class FakeSerial:
            def __init__(self, **kwargs):
                self.port = None
                self.in_waiting = 512
                self.chunks = iter([
                    b'garbage\n{"type":"hello","device":"other","v":1}\n',
                    b'{"type":"hello","device":"codex-',
                    b'quota-monitor","v":1}\n{"type":"refresh","v":1}\n',
                ])
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, _count): return next(self.chunks)
            def write(self, data):
                sent.append(json.loads(data))
                stop.set()
        packet = normalize(example(), 1000)
        bridge = SerialBridge({}, lambda: packet, lambda: refreshed.append(True), connected.append, stop)
        with patch("quota_monitor.bridge.serial.Serial", FakeSerial):
            bridge._connect("COM9")
        self.assertEqual(connected, ["COM9"])
        self.assertEqual(refreshed, [True])
        self.assertEqual(sent[0]["sampled_at"], 1000)
        self.assertEqual(sent[0]["type"], "quota")


if __name__ == "__main__":
    unittest.main()
