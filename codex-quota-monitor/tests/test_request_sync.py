import threading
import unittest
from unittest.mock import Mock, patch
from quota_monitor.desktop import is_desktop_path
from quota_monitor.service import Monitor
from test_monitor import example


class RequestSyncTests(unittest.TestCase):
    def monitor(self):
        monitor = Monitor({'device_protocol':'brookesia'})
        monitor.persist = Mock()
        return monitor

    def test_query_requires_both_request_and_running_desktop(self):
        monitor = self.monitor()
        with patch('quota_monitor.service.CodexClient') as client, patch('quota_monitor.service.is_codex_running', return_value=False):
            self.assertFalse(monitor.poll_once('request-1'))
            client.assert_not_called()
        with patch('quota_monitor.service.CodexClient') as client, patch('quota_monitor.service.is_codex_running', return_value=True):
            self.assertFalse(monitor.poll_once())
            client.assert_not_called()

    def test_response_matches_request_and_query_helper_exits(self):
        monitor = self.monitor()
        with patch('quota_monitor.service.CodexClient') as client, patch('quota_monitor.service.is_codex_running', return_value=True):
            client.return_value.read_quota.return_value = example()
            self.assertTrue(monitor.poll_once('request-1'))
            self.assertEqual(monitor.get_snapshot()['request_id'], 'request-1')
            client.return_value.close.assert_called_once()
        self.assertIsNone(monitor.client)

    def test_error_keeps_real_numbers_but_acknowledges_new_request(self):
        monitor = self.monitor()
        with patch('quota_monitor.service.CodexClient') as client, patch('quota_monitor.service.is_codex_running', return_value=True):
            client.return_value.read_quota.return_value = example()
            self.assertTrue(monitor.poll_once('first'))
            old = monitor.get_snapshot()
            client.return_value.read_quota.side_effect = TimeoutError()
            self.assertFalse(monitor.poll_once('second'))
        result = monitor.get_snapshot()
        self.assertEqual(result['request_id'], 'second')
        self.assertEqual(result['windows'], old['windows'])
        self.assertEqual(result['sampled_at'], old['sampled_at'])
        self.assertEqual(result['status'], 'error')

    def test_closing_desktop_during_query_discards_result(self):
        monitor = self.monitor()
        with patch('quota_monitor.service.CodexClient') as client, patch('quota_monitor.service.is_codex_running', side_effect=[True,False]):
            client.return_value.read_quota.return_value = example()
            self.assertFalse(monitor.poll_once('first'))
            client.return_value.close.assert_called_once()
        self.assertIsNone(monitor.snapshot['sampled_at'])

    def test_listener_does_not_poll_without_device_request(self):
        monitor = self.monitor()
        monitor.stop = Mock(spec=threading.Event)
        monitor.stop.is_set.return_value = False
        monitor.stop.wait.return_value = True
        monitor.poll_once = Mock()
        with patch('quota_monitor.service.is_codex_running',return_value=True), patch('quota_monitor.service.ROOT') as root:
            (root / 'runtime/stop.request').exists.return_value = False
            monitor._poll_loop()
        monitor.poll_once.assert_not_called()

    def test_desktop_exit_stops_lifecycle_even_during_cloud_read(self):
        monitor = self.monitor()
        monitor.stop = Mock(spec=threading.Event)
        monitor.stop.wait.return_value = False
        with patch('quota_monitor.service.is_codex_running',return_value=False):
            monitor._lifecycle_loop()
        monitor.stop.set.assert_called_once()

    def test_query_helper_and_regular_chatgpt_are_not_codex_desktop(self):
        self.assertTrue(is_desktop_path(r'C:\Program Files\WindowsApps\OpenAI.Codex_1_x64__abc\app\ChatGPT.exe'))
        self.assertTrue(is_desktop_path(r'C:\Apps\Codex\app\Codex.exe'))
        self.assertFalse(is_desktop_path(r'C:\Program Files\WindowsApps\OpenAI.Codex_1\app\resources\codex.exe'))
        self.assertFalse(is_desktop_path(r'C:\Apps\ChatGPT\app\ChatGPT.exe'))
