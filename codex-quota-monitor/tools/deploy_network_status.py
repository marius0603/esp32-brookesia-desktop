"""Stage the network status app updates while retaining installed app resources."""
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
COMMON_FILES = ("manifest.json", "app/main.js", "res/root.json")
APPS = {
    "local.radio": COMMON_FILES,
    "local.weather": COMMON_FILES + ("res/screens/main.json",),
    "local.voiceassistant": COMMON_FILES,
    "local.codex.quota": COMMON_FILES + ("res/screens/main.json",),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM5")
    args = parser.parse_args()
    versions = json.loads((ROOT / "versions.json").read_bytes())
    checksums = json.loads((ROOT / "packages/SHA256.json").read_bytes())
    payloads = {}
    for app_id, names in APPS.items():
        version = versions["apps"][app_id]
        relative = f"packages/apps/{app_id}.debug.{version}.bpk"
        path = ROOT / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == checksums[relative]
        with zipfile.ZipFile(path) as package:
            assert package.testzip() is None
            payloads[app_id] = {name: package.read(name) for name in names}
        manifest = json.loads(payloads[app_id]["manifest.json"])["package"]
        assert (manifest["id"], manifest["version"]) == (app_id, version)

    stamp = f"network-status-{time.time_ns()}"
    folder = RUNTIME / stamp
    folder.mkdir()
    report = {}
    with SharedPowerDiagnosticClient(args.port, timeout=30) as client:
        client.hello()

        def call(service, name, **params):
            return client.call_timeout(service, name, params)["result"]

        def storage(name, **params):
            return call("Storage", name, **params)

        def inspect(path):
            return call("SdResources", "InspectTree", Path=path)["sha256"]

        assert call("DeviceModes", "GetState")["firmware_version"] == versions["firmware"]
        deadline = time.monotonic() + 90
        while True:
            apps = {a["manifest"]["id"]: a for a in call("SystemCore", "ListApps")}
            if APPS.keys() <= apps.keys():
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Waiting for SD applications to become available")
            time.sleep(1)
        for app_id, files in payloads.items():
            target = f"/sdcard/apps/{app_id}"
            assert storage("FSStat", Path=f"{target}/manifest.json")["exists"]
            call("SystemCore", "StopApp", AppId=apps[app_id]["app_id"])
            prefix = f"/sdcard/resource-backups/{stamp}-{app_id}"
            stage, backup, checked = prefix + "-stage", prefix + "-previous", prefix + "-check"
            storage("FSCopyTree", From=target, To=stage, Overwrite=False)
            storage("FSMkdir", Path=checked)
            verified = {}
            for index, (name, data) in enumerate(files.items()):
                upload = folder / "transfer.bin"
                upload.write_bytes(data)
                remote = f"{stamp}.bin"
                receipt = client.transfer("put", upload, f"sd-themes/{remote}", False)
                assert receipt["ok"] and receipt["sha256"] == hashlib.sha256(data).hexdigest()
                tempfile = f"/sdcard/themes/{remote}"
                storage("FSCopyTree", From=tempfile, To=f"{stage}/{name}", Overwrite=True)
                storage("FSRemove", Path=tempfile)
                storage("FSCopyTree", From=f"{stage}/{name}", To=f"{checked}/{index}", Overwrite=False)
                verified[str(index)] = data
            assert inspect(checked) == tree_hash(verified)
            staged = inspect(stage)
            storage("FSRename", From=target, To=backup)
            try:
                storage("FSRename", From=stage, To=target)
                assert inspect(target) == staged
            except BaseException:
                if storage("FSStat", Path=target)["exists"]:
                    storage("FSRename", From=target, To=stage)
                storage("FSRename", From=backup, To=target)
                raise
            report[app_id] = {"version": versions["apps"][app_id], "backup": backup, "tree_sha256": staged}
            (folder / "deployment.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(f"{app_id} staged and verified.", flush=True)
    print("Restart the device to register the updated versions.", flush=True)


if __name__ == "__main__":
    main()
