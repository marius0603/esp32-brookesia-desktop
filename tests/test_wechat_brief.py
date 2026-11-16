import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('wechat_brief', Path(__file__).resolve().parents[1] / 'tools/wechat_brief.py')
brief = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brief)


class WechatBriefTests(unittest.TestCase):
    def test_delivery_and_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(dict(channel='openclaw-weixin', node='node', cli='cli', account='account', target='recipient')))
            response = subprocess.CompletedProcess([], 0, '{"payload":{"deliveryStatus":"sent"}}', '')
            with patch.object(brief.subprocess, 'run', return_value=response) as run:
                self.assertEqual(brief.send(path, '完成', 'commit')['status'], 'sent')
                self.assertEqual(brief.send(path, '完成', 'commit')['previous'], 'sent')
                run.assert_called_once()

    def test_failure_timeout_and_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(dict(channel='openclaw-weixin', node='node', cli='cli', account='account', target='recipient')))
            response = subprocess.CompletedProcess([], 0, '{"payload":{"deliveryStatus":"failed"}}', '')
            with patch.object(brief.subprocess, 'run', return_value=response):
                self.assertEqual(brief.send(path, '完成', 'failed')['status'], 'failed')
            with patch.object(brief.subprocess, 'run', side_effect=subprocess.TimeoutExpired('node', 55)) as run:
                with self.assertRaises(subprocess.TimeoutExpired):
                    brief.send(path, '完成', 'timeout')
                self.assertEqual(brief.send(path, '完成', 'timeout')['previous'], 'uncertain')
                run.assert_called_once()
            with patch.object(brief.subprocess, 'run') as run:
                self.assertEqual(brief.send(path, '完成', 'dry', True)['status'], 'dry_run')
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
