"""Build the standalone Android RSSI sampler with the remote's pinned toolchain."""
import argparse
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'phone-remote/rssi-calibration'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    if work.is_relative_to(ROOT):
        parser.error('Keep calibration build output and signing keys outside the repository')
    tools = json.loads(args.tools.read_text(encoding='utf-8'))
    classes, dex = work / 'classes', work / 'dex'
    classes.mkdir(parents=True, exist_ok=True)
    dex.mkdir(exist_ok=True)

    def run(*command):
        subprocess.run([str(part) for part in command], check=True)

    run(tools['javac'], '-encoding', 'UTF-8', '--release', '8', '-classpath', tools['android'],
        '-d', classes, SOURCE / 'CalibrationActivity.java')
    jar = work / 'sampler.jar'
    run(tools['jar'], 'cf', jar, '-C', classes, '.')
    run(tools['java'], '-cp', tools['d8'], 'com.android.tools.r8.D8', '--lib', tools['android'],
        '--min-api', '26', '--output', dex, jar)
    manifest = SOURCE / 'AndroidManifest.xml'
    unsigned = work / 'sampler-unsigned.apk'
    run(tools['aapt2'], 'link', '-I', tools['android'], '--manifest', manifest, '-o', unsigned)
    with zipfile.ZipFile(unsigned, 'a', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(dex / 'classes.dex', 'classes.dex')
    key = work / 'calibration-signing.jks'
    if not key.exists():
        run(tools['keytool'], '-genkeypair', '-keystore', key, '-storepass', 'android', '-keypass', 'android',
            '-alias', 'rssi', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '3650',
            '-dname', 'CN=XiaoMa RSSI Calibration')
    signed = work / 'sampler-signed.apk'
    run(tools['java'], '-jar', tools['signer'], 'sign', '--v4-signing-enabled', 'false', '--ks', key,
        '--ks-pass', 'pass:android', '--out', signed, unsigned)
    run(tools['java'], '-jar', tools['signer'], 'verify', '--verbose', signed)
    version = ET.parse(manifest).getroot().attrib['{http://schemas.android.com/apk/res/android}versionName']
    output = ROOT / f'packages/android/xiaoma-rssi-calibration-{version}.apk'
    shutil.copy2(signed, output)
    index = ROOT / 'packages/SHA256.json'
    hashes = json.loads(index.read_text(encoding='utf-8'))
    hashes[output.relative_to(ROOT).as_posix()] = hashlib.sha256(output.read_bytes()).hexdigest()
    index.write_text(json.dumps(hashes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
