"""Pack the quota App's native JSON/JS/PNG resources without a Node toolchain."""
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    app = Path(__file__).resolve().parents[2] / 'brookesia-apps/codex-quota'
    source = app / 'src'
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['package']['id'] == 'local.codex.quota'
    assert manifest['runtime']['entry'] == 'app/main.js'
    version = manifest['package']['version']
    assert json.loads((source / 'res/root.json').read_text(encoding='utf-8'))['version'] == version
    output = app / 'dist' / ('local.codex.quota.debug.' + version + '.bpk')
    output.parent.mkdir(parents=True, exist_ok=True)
    # The installed firmware supports these PNGs directly. Stable metadata makes
    # identical source bytes produce identical packages on every computer.
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob('*')):
            if not path.is_file():
                continue
            if path.suffix == '.json':
                json.loads(path.read_text(encoding='utf-8'))
            entry = zipfile.ZipInfo(path.relative_to(source).as_posix(), (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
    print(output)
    print('SHA256:', hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
