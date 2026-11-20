"""Stage and verify the matched square launcher screen and template."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from maintenance_client import SharedPowerDiagnosticClient

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "codex-quota-monitor/runtime"
SHELL = "/littlefs/system/super/shell"
FILES = ("screens/app_launcher.json", "templates/launcher_app_button.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM5")
    parser.add_argument("--restore", type=Path, help="Private launcher backup directory")
    args = parser.parse_args()
    source = args.restore or ROOT / "packages/resources/square-ui-launcher"
    token = f"square-launcher-{time.time_ns()}"
    backup = RUNTIME / token
    data = {name: (source / Path(name).name).read_bytes() for name in FILES}
    for payload in data.values():
        json.loads(payload)
    if not args.restore:
        build_inputs = json.loads((ROOT / "tools/build-inputs.json").read_bytes())["sha256"]
        for name, payload in data.items():
            relative = (source / Path(name).name).relative_to(ROOT).as_posix()
            if hashlib.sha256(payload).hexdigest() != build_inputs[relative]:
                raise ValueError(f"Launcher checksum mismatch: {name}")
    backup.mkdir(exist_ok=False)

    with SharedPowerDiagnosticClient(args.port, timeout=25) as client:
        client.hello()

        def call(service, function, **params):
            return client.call_timeout(service, function, params, 12000)["result"]

        def storage(function, **params):
            return call("Storage", function, **params)

        if not args.restore:
            expected = json.loads((ROOT / "versions.json").read_bytes())["firmware"]
            if call("DeviceModes", "GetState")["firmware_version"] != expected:
                raise RuntimeError(f"Square launcher requires firmware {expected}")

        originals = {}
        for name in FILES:
            text = storage("FSReadText", Path=f"{SHELL}/{name}")
            originals[name] = text.encode("utf-8")
            (backup / Path(name).name).write_bytes(originals[name])

        staged_files = []

        def stage(payload, suffix):
            local = backup / suffix
            local.write_bytes(payload)
            transfer = client.transfer("put", local, "sd-themes/" + token + "-" + suffix, False)
            if not transfer["ok"] or transfer["sha256"] != hashlib.sha256(payload).hexdigest():
                raise RuntimeError(f"Launcher transfer failed: {suffix}")
            remote = "/sdcard/themes/" + token + "-" + suffix
            staged_files.append(remote)
            return remote

        touched = []
        try:
            files = {name: stage(data[name], f"new-{index}.json") for index, name in enumerate(FILES)}
            for name, remote in files.items():
                touched.append(name)
                storage("FSCopyTree", From=remote, To=f"{SHELL}/{name}", Overwrite=True)
                written = storage("FSReadText", Path=f"{SHELL}/{name}").encode("utf-8")
                if written != data[name]:
                    raise RuntimeError(f"Launcher read-back mismatch: {name}")
        except Exception:
            for index, name in enumerate(touched):
                original = stage(originals[name], f"restore-{index}.json")
                storage("FSCopyTree", From=original, To=f"{SHELL}/{name}", Overwrite=True)
                written = storage("FSReadText", Path=f"{SHELL}/{name}").encode("utf-8")
                if written != originals[name]:
                    raise RuntimeError(f"Launcher backup restore failed: {backup}")
            raise
        finally:
            for remote in staged_files:
                try:
                    storage("FSRemove", Path=remote)
                except RuntimeError:
                    pass

    print(f"Launcher files verified. Private backup: {backup}")


if __name__ == "__main__":
    main()
