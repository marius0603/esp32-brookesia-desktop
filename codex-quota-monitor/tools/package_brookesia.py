"""Package only the built firmware, public sources, and version evidence."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
repo = root.parent / 'esp-brookesia-v08'
project = repo / 'examples/system/super_s3_216'
build = project / 'build'
app = root.parent / 'brookesia-apps/codex-quota'
args = json.loads((build / 'flasher_args.json').read_text())
desc = json.loads((build / 'project_description.json').read_text())
output = root / f"artifacts/brookesia-{desc['project_version']}.zip"
output.parent.mkdir(exist_ok=True)
manifest = {'project': desc['project_name'], 'version': desc['project_version'],
            'upstream_commit': '68ac00e7aa9012cd8cbf0cbf6bee155801db0e8c', 'files': {}}
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    def add(path, name):
        archive.write(path, name)
        manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    for relative in args['flash_files'].values():
        add(build / relative, 'firmware/' + Path(relative).as_posix())
    add(build / 'flasher_args.json', 'firmware/flasher_args.json')
    add(root / 'BROOKESIA.md', 'BROOKESIA.md')
    add(root / 'BROOKESIA_VERIFICATION.md', 'BROOKESIA_VERIFICATION.md')
    add(root / 'tools/brookesia-s3-adaptation.patch', 'patches/brookesia-s3-adaptation.patch')
    for path in (root / 'quota_monitor').glob('*.py'):
        add(path, 'computer/quota_monitor/' + path.name)
    for name in ('requirements.txt', 'start.ps1', 'stop.ps1', 'setup.ps1'):
        add(root / name, 'computer/' + name)
    for name in ('brookesia_device.py', 'brookesia_idf6.py', 'build_quota_bpk.py', 'flash_brookesia.py',
                 'capture_brookesia_boot.py', 'restore_factory.py', 'verify_brookesia_ui.py'):
        add(root / 'tools' / name, 'computer/tools/' + name)
    archive.writestr('computer/config.example.json', json.dumps({
        'codex_path': '', 'poll_seconds': 60, 'stale_seconds': 180,
        'serial_port': 'auto', 'baudrate': 115200, 'device_protocol': 'brookesia',
        'warning_percent': 20, 'critical_percent': 10,
    }, indent=2))
    add(project / 'sdkconfig', 'system-source/sdkconfig')
    for path in project.rglob('*'):
        relative = path.relative_to(project)
        if path.is_file() and not any(part in {'build', 'managed_components', '.cache', '__pycache__'} for part in relative.parts):
            if path.name not in {'sdkconfig', 'sdkconfig.old', '.DS_Store'}:
                add(path, 'system-source/' + relative.as_posix())
    for path in app.rglob('*'):
        relative = path.relative_to(app)
        if path.is_file() and relative.parts[0] in {'src', 'dist'}:
            add(path, 'quota-app/' + relative.as_posix())
    board = repo / 'hal/brookesia_hal_boards/boards/waveshare/esp32_s3_touch_amoled_2_16/board_devices.yaml'
    add(board, 'board/board_devices.yaml')
    archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
with zipfile.ZipFile(output) as archive:
    if archive.testzip() is not None:
        raise SystemExit('Archive integrity check failed')
print(output)
print('SHA256:', hashlib.sha256(output.read_bytes()).hexdigest())
