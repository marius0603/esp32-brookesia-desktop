"""Encrypt/restore an Android signing keystore; plaintext and passwords stay outside Git."""
import argparse
import base64
import getpass
import json
import os
from pathlib import Path
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

ROOT = Path(__file__).resolve().parents[2]
AAD = b'xiaoma-signing-backup:v1:scrypt-32768-8-1:aes256gcm'

def external(path):
    path = path.resolve()
    if path.is_relative_to(ROOT):
        raise ValueError('Plaintext keys and password files must be outside the repository')
    return path

def seal(data, password):
    if len(password) < 20:
        raise ValueError('Use an encryption password of at least 20 characters')
    salt, nonce = os.urandom(16), os.urandom(12)
    key = Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(password.encode('utf-8'))
    cipher = AESGCM(key).encrypt(nonce, data, AAD)
    return json.dumps({'format':'xiaoma-signing-v1', 'salt':base64.b64encode(salt).decode(),
                       'nonce':base64.b64encode(nonce).decode(), 'ciphertext':base64.b64encode(cipher).decode()}, indent=2).encode()+b'\n'

def unseal(data, password):
    if len(data) > 256*1024:
        raise ValueError('Unexpected backup size')
    obj = json.loads(data)
    if obj['format'] != 'xiaoma-signing-v1':
        raise ValueError('Unsupported backup format')
    salt, nonce, cipher = [base64.b64decode(obj[k], validate=True) for k in ('salt','nonce','ciphertext')]
    if len(salt) != 16 or len(nonce) != 12 or not 16 <= len(cipher) <= 128*1024:
        raise ValueError('Invalid backup envelope')
    key = Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(password.encode('utf-8'))
    return AESGCM(key).decrypt(nonce, cipher, AAD)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['encrypt','decrypt'])
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--password-file', type=Path)
    a = p.parse_args()
    if a.output.exists():
        p.error('Choose a new output file; existing keys are never overwritten')
    if a.operation == 'encrypt':
        external(a.input)
        if a.output.suffix != '.enc':
            p.error('Encrypted backup must use the .enc extension')
    else:
        external(a.output)
    if a.password_file:
        password = external(a.password_file).read_text(encoding='utf-8-sig').strip()
    else:
        password = getpass.getpass('Encryption password: ')
        if a.operation == 'encrypt' and password != getpass.getpass('Confirm encryption password: '):
            p.error('Passwords do not match')
    try:
        result = (seal if a.operation == 'encrypt' else unseal)(a.input.read_bytes(), password)
    except InvalidTag:
        p.error('Incorrect password or damaged backup; no output written')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('xb') as f:
        f.write(result)
    print('Encrypted backup created.' if a.operation == 'encrypt' else 'Signing key restored outside Git.')

if __name__ == '__main__':
    main()
