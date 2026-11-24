"""Install and verify the self-contained pet BPK, keeping a rollback copy."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile

from deploy_clock_widgets import tree_hash
from maintenance_client import SharedPowerDiagnosticClient

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "codex-quota-monitor/runtime"
APP_ID = "local.virtualpet"
INSTALL_DIR = f"/sdcard/apps/{APP_ID}"
SLEEP_CONFIG = "/sdcard/pets/xiaoli/schedule.json"


def read_package():
    version = json.loads((ROOT / "versions.json").read_bytes())["apps"][APP_ID]
    name = f"packages/apps/{APP_ID}.debug.{version}.bpk"
    package = ROOT / name
    hashes = json.loads((ROOT / "packages/SHA256.json").read_bytes())
    assert hashlib.sha256(package.read_bytes()).hexdigest() == hashes[name]
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        files = {path: archive.read(path) for path in archive.namelist()}
    manifest = json.loads(files["manifest.json"])["package"]
    assert (manifest["id"], manifest["version"]) == (APP_ID, version)
    return package, version, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    package, version, files = read_package()
    stamp = f"/sdcard/resource-backups/virtual-pet-{time.time_ns()}"
    with SharedPowerDiagnosticClient(args.port, timeout=35) as client:
        client.hello()

        def call(service, function, **params):
            return client.call_timeout(service, function, params)["result"]

        def exists(path):
            return call("Storage", "FSStat", Path=path)["exists"]

        def digest(path):
            return call("SdResources", "InspectTree", Path=path)["sha256"]

        assert not call("DeviceModes", "GetState")["screen_locked"]
        existing = next((app for app in call("SystemCore", "ListApps")
                         if app["manifest"]["id"] == APP_ID), None)
        if existing:
            if existing["state"] in ("Running", "Paused", "Starting"):
                call("SystemCore", "StopApp", AppId=existing["app_id"])
            previous = INSTALL_DIR if exists(INSTALL_DIR) else f"/littlefs/apps/{APP_ID}"
            assert exists(previous)
            call("Storage", "FSCopyTree", From=previous, To=stamp + "/app", Overwrite=False)
            if previous == INSTALL_DIR:
                assert digest(previous) == digest(stamp + "/app")
            else:
                assert call("Storage", "FSReadText", Path=previous + "/manifest.json") == call(
                    "Storage", "FSReadText", Path=stamp + "/app/manifest.json"
                )

        sleep_config = call("Storage", "FSReadText", Path=SLEEP_CONFIG) if exists(SLEEP_CONFIG) else None
        layout = call("SystemCore", "GetStorageLayout")
        try:
            call("SystemCore", "SetDefaultInstallStorage", Target="External")
            assert client.transfer("install_bpk", package, None, False)["ok"]
        finally:
            call("SystemCore", "SetDefaultInstallStorage", Target=layout["default_install_target"],
                 PreferredExternalId=layout.get("preferred_external_id", ""))
        installed = next(app for app in call("SystemCore", "ListApps") if app["manifest"]["id"] == APP_ID)
        assert installed["manifest"]["version"] == version
        assert digest(INSTALL_DIR) == tree_hash(files)
        if sleep_config is not None:
            assert call("Storage", "FSReadText", Path=SLEEP_CONFIG) == sleep_config
    RUNTIME.mkdir(exist_ok=True)
    (RUNTIME / "virtual-pet-deployment.json").write_text(
        json.dumps({"version": version, "backup": stamp if existing else None,
                    "installed_tree_sha256": tree_hash(files)}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Pet {version} installed and verified on SD. Previous app retained for rollback.", flush=True)


if __name__ == "__main__":
    main()
