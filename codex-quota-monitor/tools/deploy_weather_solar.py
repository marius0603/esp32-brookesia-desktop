"""Update the installed SD weather app while preserving its data and theme assets."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile

from maintenance_client import SharedPowerDiagnosticClient


ROOT = Path(__file__).resolve().parents[2]
APP_ID = "local.weather"
INSTALL_DIR = f"/sdcard/apps/{APP_ID}"
IMAGE_INDEX = "res/images/index.json"
UPDATE_FILES = ("app/main.js", "res/screens/main.json", "manifest.json")


def read_release(version: str) -> tuple[dict[str, bytes], list[dict]]:
    package = ROOT / f"packages/apps/{APP_ID}.debug.{version}.bpk"
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None:
            raise ValueError("Weather package failed its ZIP integrity check")
        files = {name: archive.read(name) for name in UPDATE_FILES}
        manifest = json.loads(files["manifest.json"])["package"]
        if (manifest["id"], manifest["version"]) != (APP_ID, version):
            raise ValueError("Weather package ID or version does not match")
        index = json.loads(archive.read(IMAGE_INDEX))
        tiles = [image for image in index["images"] if image["id"].startswith("sky_")]
        for tile in tiles:
            name = tile["id"] + ".bin"
            if tile["src"] != name or Path(name).name != name:
                raise ValueError(f"Invalid sky texture name: {name}")
            path = "res/images/" + name
            files[path] = archive.read(path)
    return files, tiles


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    version = json.loads((ROOT / "versions.json").read_text(encoding="utf-8"))["apps"][APP_ID]
    files, tiles = read_release(version)
    token = f"weather-{time.time_ns()}"
    root = "/sdcard/resource-backups"
    stage, saved = f"{root}/{token}-ready", f"{root}/{token}-previous"
    folder = ROOT / "codex-quota-monitor/runtime" / token
    folder.mkdir()

    with SharedPowerDiagnosticClient(args.port, timeout=30) as client:
        client.hello()

        def call(service, name, **params):
            return client.call_timeout(service, name, params)["result"]

        def storage(name, **params):
            return call("Storage", name, **params)

        def tree(path):
            return call("SdResources", "InspectTree", Path=path)

        app = next(a for a in call("SystemCore", "ListApps") if a["manifest"]["id"] == APP_ID)
        if not storage("FSStat", Path=f"{INSTALL_DIR}/manifest.json")["exists"]:
            raise RuntimeError("Weather is not installed on the SD card")
        call("SystemCore", "StopApp", AppId=app["app_id"])

        installed_index = json.loads(storage("FSReadText", Path=f"{INSTALL_DIR}/{IMAGE_INDEX}"))
        if tiles:
            tile_ids = {tile["id"] for tile in tiles}
            existing = [image for image in installed_index["images"] if image["id"] not in tile_ids]
            installed_index["images"] = existing + tiles
            files[IMAGE_INDEX] = (json.dumps(installed_index, ensure_ascii=False, indent=2) + "\n").encode()
        storage("FSCopyTree", From=INSTALL_DIR, To=stage, Overwrite=False)

        verified_files = {}
        upload = folder / "transfer.bin"
        remote = f"sd-themes/{token}.bin"
        temp_path = f"/sdcard/themes/{token}.bin"
        for name, payload in files.items():
            upload.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            result = client.transfer("put", upload, remote, False)
            if not result["ok"] or result["sha256"] != digest:
                raise RuntimeError(f"Weather upload verification failed for {name}")
            storage("FSCopyTree", From=temp_path, To=f"{stage}/{name}", Overwrite=True)
            storage("FSRemove", Path=temp_path)
            if storage("FSStat", Path=f"{stage}/{name}")["size"] != len(payload):
                raise RuntimeError(f"Staged file has an unexpected size: {name}")
            verified_files[name] = digest
        staged_hash = tree(stage)["sha256"]

        storage("FSRename", From=INSTALL_DIR, To=saved)
        try:
            storage("FSRename", From=stage, To=INSTALL_DIR)
        except BaseException:
            # A transport failure may arrive after the rename completed.
            if not storage("FSStat", Path=INSTALL_DIR)["exists"]:
                storage("FSRename", From=saved, To=INSTALL_DIR)
            raise
        if tree(INSTALL_DIR)["sha256"] != staged_hash:
            raise RuntimeError(f"Installed tree differs. Original resources are at {saved}")

    report = {"version": version, "backup": saved, "tree_sha256": staged_hash, "files": verified_files}
    (folder / "deployment.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Weather {version} is installed and verified. Restart to register the new manifest.")


if __name__ == "__main__":
    main()
