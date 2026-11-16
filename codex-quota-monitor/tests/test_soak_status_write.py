import ctypes
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from verify_audio_soak import replace_status


class StatusWriteTests(unittest.TestCase):
    def test_temporary_reader_conflict_retries(self):
        temp = Mock()
        temp.replace.side_effect = [PermissionError(), None]
        with patch('verify_audio_soak.time.sleep'):
            replace_status(temp, 'status.json')
        self.assertEqual(temp.replace.call_count, 2)

    def test_permanent_failure_is_not_hidden(self):
        temp = Mock()
        temp.replace.side_effect = PermissionError()
        with patch('verify_audio_soak.time.sleep'):
            with self.assertRaises(PermissionError):
                replace_status(temp, 'status.json')
        self.assertEqual(temp.replace.call_count, 61)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows sharing semantics')
    def test_real_windows_reader_denying_delete(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                      ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        with tempfile.TemporaryDirectory() as folder:
            target, temp = Path(folder) / 'status.json', Path(folder) / 'status.tmp'
            target.write_text('{"old":true}')
            temp.write_text('{"new":true}')
            handle = kernel.CreateFileW(str(target), 0x80000000, 3, None, 3, 0, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
            try:
                with self.assertRaises(PermissionError):
                    temp.replace(target)
                release = threading.Timer(.15, kernel.CloseHandle, [handle])
                release.start()
                replace_status(temp, target)
                release.join()
                handle = None
                self.assertEqual(target.read_text(), '{"new":true}')
            finally:
                if handle:
                    kernel.CloseHandle(handle)


if __name__ == '__main__':
    unittest.main()
