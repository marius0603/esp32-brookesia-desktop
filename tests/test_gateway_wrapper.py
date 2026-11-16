"""Exercise the actual compiled Windows launcher, including its CMD boundary."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

CSC = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
SOURCE = Path(__file__).resolve().parents[1] / 'tools/windows/GatewayProxyWrapper.cs'


@unittest.skipUnless(os.name == 'nt' and CSC.exists(), 'Windows .NET compiler required')
class GatewayWrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='gateway wrapper test ')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binary = Path(cls.directory.name) / 'wrapper.exe'
        subprocess.run([str(CSC), '/nologo', '/target:exe', '/out:' + str(cls.binary), str(SOURCE)],
                       check=True, capture_output=True)

    def test_shell_text_is_rejected_before_launch(self):
        for argument in ['a b', 'x&y', '%PATH%', 'x|y', 'x\ny', 'x"y']:
            with self.subTest(argument=argument):
                result = subprocess.run([str(self.binary), argument], capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 2)
                self.assertIn(b'Unsupported gateway launcher argument', result.stderr)

    def test_version_through_cmd_parent(self):
        if not Path('D:/chatgpt_data/tools/openclaw-runtime/cli/node_modules/openclaw/openclaw.mjs').exists():
            self.skipTest('Host-specific OpenClaw runtime is not installed')
        result = subprocess.run([str(self.binary), '--version'], capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b'OpenClaw', result.stdout)


if __name__ == '__main__':
    unittest.main()
