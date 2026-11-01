"""Security regressions for the portable encrypted signing backup."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from signing_backup import seal, unseal
from cryptography.exceptions import InvalidTag

class SigningBackupTests(unittest.TestCase):
    password = 'test-only-password-with-at-least-20-characters'

    def test_roundtrip_and_random_encryption(self):
        first, second = seal(b'private-key-test', self.password), seal(b'private-key-test', self.password)
        self.assertNotEqual(first, second)
        self.assertEqual(unseal(first, self.password), b'private-key-test')

    def test_wrong_password_and_tampered_ciphertext(self):
        encrypted = seal(b'private-key-test', self.password)
        with self.assertRaises(InvalidTag):
            unseal(encrypted, 'different-password')
        obj = json.loads(encrypted)
        value = bytearray(base64.b64decode(obj['ciphertext']))
        value[0] ^= 1
        obj['ciphertext'] = base64.b64encode(value).decode()
        with self.assertRaises(InvalidTag):
            unseal(json.dumps(obj).encode(), self.password)

    def test_invalid_format_and_password(self):
        with self.assertRaises(ValueError):
            seal(b'private-key-test', 'too-short')
        with self.assertRaises(ValueError):
            unseal(b'X' * (256*1024+1), self.password)

    def test_failed_cli_decryption_writes_no_plaintext(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            encrypted, password, output = folder/'key.enc', folder/'password.txt', folder/'restore.jks'
            encrypted.write_bytes(seal(b'private-key-test', self.password))
            password.write_text('wrong-password', encoding='utf-8')
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'tools/signing_backup.py'),
                                     'decrypt', '--input', str(encrypted), '--output', str(output),
                                     '--password-file', str(password)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            output.write_bytes(b'existing-key')
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'tools/signing_backup.py'),
                                     'decrypt', '--input', str(encrypted), '--output', str(output),
                                     '--password-file', str(password)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b'existing-key')

if __name__ == '__main__':
    unittest.main()
