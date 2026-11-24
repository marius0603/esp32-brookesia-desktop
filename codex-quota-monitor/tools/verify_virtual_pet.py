"""Verify released pet resources and replay gesture payloads on the board."""
import argparse
import hashlib
import json
import time

from deploy_virtual_pet import APP_ID, INSTALL_DIR, RUNTIME, read_package
from deploy_clock_widgets import tree_hash
from maintenance_client import SharedPowerDiagnosticClient


REPLAY = r"""
const qaDay = Date.parse('2026-11-24T09:00:00+08:00');
const qaPoint = { x: 170, y: 180 };
const qaDrag = { x: 291, y: 89 };
const qaReport = {};
const qaSteps = [
  ['idle', 0, now => tick(now), 'eye_open', 70, 150, 30],
  ['tap', 100, now => {
    act('facePress', qaPoint, now);
    act('faceRelease', qaPoint, now);
  }, 'eye_happy', 70, 180, 30],
  ['doubleTap', 270, now => {
    act('facePress', qaPoint, now);
    act('faceRelease', qaPoint, now);
  }, 'eye_surprised', 70, 120, 20],
  ['holdStart', 1500, now => {
    tick(now);
    act('facePress', qaPoint, now);
  }, 'eye_open', 70, 150, 30],
  ['hold', 2050, now => tick(now), 'eye_calm', 70, 200, 50],
  ['holdRelease', 2100, now => act('faceRelease', qaPoint, now), 'eye_calm', 70, 200, 50],
  ['drag', 2800, now => {
    act('facePress', qaPoint, now);
    act('faceMove', qaDrag, now);
    for (let i = 0; i < 4; i++) tick(now + i * 45);
  }, 'eye_open', 110, 120, 20],
  ['recenter', 3040, now => {
    act('faceRelease', qaDrag, now);
    for (let i = 1; i < 4; i++) tick(now + i * 45);
  }, 'eye_open', 70, 150, 30],
  ['returnStrip', 3300, now => {
    act('facePress', { x: 240, y: 455 }, now);
    act('faceMove', { x: 240, y: 320 }, now);
    act('faceRelease', { x: 240, y: 320 }, now);
    if (press) throw Error('Pet intercepted bottom swipe');
    tick(now);
  }, 'eye_open', 70, 150, 30],
  ['blink', 3900, now => tick(now), 'eye_blink', 70, 200, 30],
  ['sleep', 13 * 3600000, now => {
    tick(now);
    act('facePress', qaPoint, now);
    act('faceRelease', qaPoint, now);
  }, 'eye_sleep', 70, 210, 50],
];
let qaIndex = 0;
globalThis.brookesia_app.on_timer = function () {
  if (qaIndex >= qaSteps.length) return true;
  let error = '';
  try {
    if (qaIndex === 0) sleep = { start: 1320, end: 420 };
    const [label, elapsed, run, asset, x, y, ears] = qaSteps[qaIndex++];
    run(qaDay + elapsed);
    const left = call(gui, 'GetViewFrame', { Path: '/main/left' });
    const right = call(gui, 'GetViewFrame', { Path: '/main/right' });
    const crown = call(gui, 'GetViewFrame', { Path: '/main/crown' });
    const mouth = call(gui, 'GetViewFrame', { Path: '/main/mouth' });
    if (rendered.eye !== asset || left.x !== x || right.x !== x + 210 ||
        left.y !== y || right.y !== y || crown.y !== ears || mouth.width !== 80) {
      throw Error(label + ': ' + JSON.stringify({ rendered, left, right, crown, mouth }));
    }
    qaReport[label] = [left.x, left.y, crown.y, rendered.eye];
  } catch (failure) {
    error = String(failure);
    qaIndex = qaSteps.length;
  }
  if (qaIndex === qaSteps.length) {
    const storage = brookesia.start_service('Storage');
    call(storage, 'FSWriteText', { Path: __REPORT_PATH__, Data: JSON.stringify({ steps: qaReport, error }) });
  }
  return true;
};
"""


def wait(read, ready, seconds=35):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            result = read()
        except RuntimeError as exc:
            if str(exc) != "call_failed: GUI busy":
                raise
        else:
            if ready(result):
                return result
        time.sleep(0.25)
    raise TimeoutError(f"Timed out waiting for {read.__name__}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    _, version, files = read_package()
    stamp = f"pet-verify-{time.time_ns()}"
    backup = f"/sdcard/resource-backups/{stamp}"
    script = files["app/main.js"].decode()
    end = "\n})();\n"
    assert script.endswith(end)
    report_path = backup + "/result.json"
    probe = REPLAY.replace("__REPORT_PATH__", json.dumps(report_path))
    RUNTIME.mkdir(parents=True, exist_ok=True)
    staged = RUNTIME / f"{stamp}.js"
    staged.write_bytes((script[:-len(end)] + probe + end).encode())

    with SharedPowerDiagnosticClient(args.port, timeout=12) as client:
        client.hello()

        def call(service, function, **params):
            return client.call_timeout(service, function, params, 15000)["result"]

        def state():
            return call("DeviceModes", "GetState")

        def active():
            return call("SystemCore", "GetActiveApp")

        def layers():
            return call("DeviceModes", "GetWeatherLayers")["layers"]

        def verify_release():
            tree = call("SdResources", "InspectTree", Path=INSTALL_DIR)
            assert tree["sha256"] == tree_hash(files), "Installed pet differs from the release"

        apps = {app["manifest"]["id"]: app for app in call("SystemCore", "ListApps")}
        pet = apps[APP_ID]
        assert pet["manifest"]["version"] == version
        pet_id = pet["app_id"]
        shell_id = apps["brookesia.system.super.shell"]["app_id"]

        def open_pet():
            call("SystemCore", "StartApp", AppId=pet_id)
            front = wait(active, lambda app: app.get("app_id") == pet_id and app.get("state") == "Running")
            assert not front.get("last_error")
            wait(layers, lambda nodes: any(n.get("rgb") == 0 and n.get("width", 0) >= 450 and
                 n.get("height", 0) >= 450 and n.get("background_opacity", 0) >= 200 for n in nodes))

        def close_pet():
            if active().get("app_id") == pet_id:
                call("SystemCore", "RequestCloseApp", AppId=pet_id)
            wait(active, lambda app: app.get("app_id") in (None, shell_id))

        initial = state()
        assert not initial["screen_locked"]
        assert active().get("app_id") in (None, pet_id, shell_id)
        call("DeviceModes", "Wake")
        close_pet()
        verify_release()
        open_pet()
        close_pet()
        print("Release opens with a black full-screen background and returns to the launcher.", flush=True)

        target = INSTALL_DIR + "/app/main.js"
        saved = backup + "/main.js"
        call("SystemCore", "StopApp", AppId=pet_id)
        call("Storage", "FSCopyTree", From=target, To=saved, Overwrite=False)
        remote = stamp + ".bin"
        result = client.transfer("put", staged, "sd-themes/" + remote, False)
        assert result["ok"] and result["sha256"] == hashlib.sha256(staged.read_bytes()).hexdigest()
        remote_path = "/sdcard/themes/" + remote
        try:
            call("Storage", "FSCopyTree", From=remote_path, To=target, Overwrite=True)
            open_pet()

            def report_ready():
                return call("Storage", "FSStat", Path=report_path)

            wait(report_ready, lambda info: info["exists"])
            report = json.loads(call("Storage", "FSReadText", Path=report_path))
            assert not report["error"], report
            assert len(report["steps"]) == 11, report
            print("Gesture and view checks passed: " + ", ".join(report["steps"]), flush=True)
        finally:
            try:
                close_pet()
                call("SystemCore", "StopApp", AppId=pet_id)
            finally:
                call("Storage", "FSCopyTree", From=saved, To=target, Overwrite=True)
                verify_release()
                call("Storage", "FSRemove", Path=remote_path)

        open_pet()
        final = state()
        assert final["uptime_ms"] > initial["uptime_ms"]
        assert final["reset_reason"] == initial["reset_reason"]
        assert final["desktop_theme_index"] == initial["desktop_theme_index"]
        print("Exact release tree restored and reopened. Device did not reset.", flush=True)


if __name__ == "__main__":
    main()
