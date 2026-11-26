"""Install the independent aquarium BPK and verify the SD installation."""
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
APP_ID = "local.aquarium"
INSTALL_DIR = f"/sdcard/apps/{APP_ID}"
SETTINGS = "/littlefs/aquarium-settings.json"
FONT_ROOT = ROOT / "platform/super_s3_216/littlefs/system/fonts"
FONT_ID = "zh_CN_aquarium"
FONT_DIR = "/littlefs/system/fonts"


def install_font(client, call):
    """Leave other font registrations intact and verify the supplement before enabling it."""
    fonts = json.loads((FONT_ROOT / "index.json").read_bytes())["fonts"]
    supplement = next(entry for entry in fonts if entry["id"] == FONT_ID)
    source = FONT_ROOT / supplement["src"]
    payload = source.read_bytes()
    target = f"{FONT_DIR}/{source.name}"
    index_path = f"{FONT_DIR}/index.json"
    original = call("Storage", "FSReadText", Path=index_path)
    index = json.loads(original)
    registered = next((entry for entry in index["fonts"] if entry["id"] == FONT_ID), None)
    chinese = next(entry for entry in index["fonts"] if entry["id"] == "zh_CN")
    reference = "${font." + FONT_ID + "}"
    stat = call("Storage", "FSStat", Path=target)
    if registered == supplement and reference in chinese.get("fallbacks", []) and stat.get("size") == len(payload):
        print("Aquarium glyph supplement already installed.", flush=True)
        return

    stamp = f"aquarium-font-{time.time_ns()}"
    backup = f"/sdcard/resource-backups/{stamp}"
    call("Storage", "FSCopyTree", From=index_path, To=f"{backup}/index.json", Overwrite=False)
    if stat["exists"]:
        call("Storage", "FSCopyTree", From=target, To=f"{backup}/{source.name}", Overwrite=False)
    staged = f"{stamp}.ttf"
    transfer = client.transfer("put", source, staged, False)
    assert transfer["ok"] and transfer["sha256"] == hashlib.sha256(payload).hexdigest()
    try:
        call("Storage", "FSRename", From=f"/littlefs/usb/{staged}", To=target)
        check = f"{backup}/verified"
        call("Storage", "FSCopyTree", From=target, To=f"{check}/{source.name}", Overwrite=False)
        assert call("SdResources", "InspectTree", Path=check)["sha256"] == tree_hash({source.name: payload})
        index["fonts"] = [entry for entry in index["fonts"] if entry["id"] != FONT_ID] + [supplement]
        fallbacks = chinese.setdefault("fallbacks", [])
        if reference not in fallbacks:
            fallbacks.append(reference)
        call("Storage", "FSWriteText", Path=index_path, Data=json.dumps(index, ensure_ascii=False, indent=2) + "\n")
        assert json.loads(call("Storage", "FSReadText", Path=index_path)) == index
    except Exception:
        call("Storage", "FSWriteText", Path=index_path, Data=original)
        if stat["exists"]:
            call("Storage", "FSCopyTree", From=f"{backup}/{source.name}", To=target, Overwrite=True)
        elif call("Storage", "FSStat", Path=target)["exists"]:
            call("Storage", "FSRemove", Path=target)
        raise
    print(f"Aquarium glyph supplement verified. Restart to load it. Backup: {backup}", flush=True)


def read_package():
    version = json.loads((ROOT / "versions.json").read_bytes())["apps"][APP_ID]
    name = f"packages/apps/{APP_ID}.debug.{version}.bpk"
    package = ROOT / name
    hashes = json.loads((ROOT / "packages/SHA256.json").read_bytes())
    assert hashlib.sha256(package.read_bytes()).hexdigest() == hashes[name]
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        files = {path: archive.read(path) for path in archive.namelist()}
    package_info = json.loads(files["manifest.json"])["package"]
    assert (package_info["id"], package_info["version"]) == (APP_ID, version)
    return package, version, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--font-only", action="store_true", help="Install the glyph supplement without replacing the BPK")
    args = parser.parse_args()
    with SharedPowerDiagnosticClient(args.port, timeout=35) as client:
        client.hello()

        def call(service, function, **params):
            return client.call_timeout(service, function, params)["result"]

        def list_apps():
            return {app["manifest"]["id"]: app for app in call("SystemCore", "ListApps")}

        def digest(path):
            return call("SdResources", "InspectTree", Path=path)["sha256"]

        assert not call("DeviceModes", "GetState")["screen_locked"]
        if args.font_only:
            install_font(client, call)
            return

        package, version, files = read_package()
        before = list_apps()
        preference = None
        if call("Storage", "FSStat", Path=SETTINGS)["exists"]:
            preference = call("Storage", "FSReadText", Path=SETTINGS)
        prior = before.get(APP_ID)
        backup = None
        if prior:
            if prior["state"] in ("Starting", "Running", "Paused"):
                call("SystemCore", "StopApp", AppId=prior["app_id"])
            backup = f"/sdcard/resource-backups/aquarium-{time.time_ns()}"
            call("Storage", "FSCopyTree", From=INSTALL_DIR, To=backup, Overwrite=False)
            assert digest(backup) == digest(INSTALL_DIR)

        layout = call("SystemCore", "GetStorageLayout")
        try:
            call("SystemCore", "SetDefaultInstallStorage", Target="External")
            assert client.transfer("install_bpk", package, None, False)["ok"]
        finally:
            call("SystemCore", "SetDefaultInstallStorage", Target=layout["default_install_target"],
                 PreferredExternalId=layout.get("preferred_external_id", ""))
        installed = list_apps()
        manifest = installed[APP_ID]["manifest"]
        assert manifest["version"] == version and manifest["visible"]
        assert set(before).issubset(installed)
        installed_hash = digest(INSTALL_DIR)
        assert installed_hash == tree_hash(files)
        if preference is not None:
            assert call("Storage", "FSReadText", Path=SETTINGS) == preference
        install_font(client, call)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / "aquarium-deployment.json").write_text(
        json.dumps({"version": version, "backup": backup, "installed_tree_sha256": installed_hash}, indent=2)
        + "\n", encoding="utf-8")
    print(f"Aquarium {version} installed on SD and verified in the desktop app list.", flush=True)


if __name__ == "__main__":
    main()
