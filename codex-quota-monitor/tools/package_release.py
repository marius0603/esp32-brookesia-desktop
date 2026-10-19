"""Collect source and already-built firmware; never include account state or toolchain caches."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
BUILD = ROOT / "firmware/build"
version = json.loads((BUILD / "project_description.json").read_text(encoding="utf-8"))["project_version"]
if version != "0.3.0":
    raise SystemExit("Reconfigure and rebuild the 0.3.0 release before packaging.")
bundle = ARTIFACTS / ("firmware-" + version)
files = ["codex_quota_monitor.bin", "bootloader/bootloader.bin", "partition_table/partition-table.bin", "quota-nvs.bin"]
hashes = {}
for name in files:
    target = bundle / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD / name, target)
    hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
flash_args = (BUILD / "flash_args").read_text(encoding="utf-8").rstrip() + "\n0xf00000 quota-nvs.bin\n"
(bundle / "flash_args").write_text(flash_args, encoding="utf-8")
hashes['flash_args'] = hashlib.sha256((bundle / 'flash_args').read_bytes()).hexdigest()
(bundle / "SHA256.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
(bundle / "README.txt").write_text(
    "Codex quota monitor 0.3.0\nBoard: Waveshare ESP32-S3-Touch-AMOLED-2.16\n"
    "ESP-IDF 5.5.5 / BSP 2.0.1 / LVGL 9.3.0\n"
    "Flashed with user authorization after a verified full device backup.\n"
    "Real quota reception, codec/PMU initialization and visible UI confirmed.\n"
    "Physical volume/PMU shutdown effects still require manual testing.\n"
    "Keep the relative paths in flash_args. Prefer tools/build-firmware.ps1 -Flash -Port COMx from the source project.\n"
    "Do not flash another board model or erase existing flash without first preserving needed data.\n",
    encoding="utf-8",
)
with zipfile.ZipFile(ARTIFACTS / ("firmware-" + version + ".zip"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(bundle.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(bundle))
tracked = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode("utf-8").split("\0")
with zipfile.ZipFile(ARTIFACTS / ("codex-quota-monitor-" + version + "-source.zip"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(set(tracked)):
        path = ROOT / name
        if not name or not path.is_file() or name.endswith(".zip") or name.startswith("artifacts/firmware"):
            continue
        archive.write(path, Path("codex-quota-monitor") / name)
print(json.dumps({"version": version, "app_bytes": (BUILD / files[0]).stat().st_size, "app_sha256": hashes[files[0]]}, indent=2))
