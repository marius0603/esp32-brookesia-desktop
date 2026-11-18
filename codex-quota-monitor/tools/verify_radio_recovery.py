"""Exercise a real station disconnect/reconnect without changing the router."""
import argparse
import json
from pathlib import Path
import time

from maintenance_client import SharedPowerDiagnosticClient

RUNTIME = Path(__file__).resolve().parents[1] / "runtime"
STATIONS = ("suzhou-qtfm", "naps-0", "cnr-classic", "junior-0", "story-quest-0")


def wait_for(read, predicate, seconds, label):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        state = read()
        if predicate(state):
            return state
        time.sleep(.25)
    raise TimeoutError(label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM5")
    parser.add_argument("--sample-seconds", type=int, default=120)
    parser.add_argument("--station", action="append", choices=STATIONS)
    args = parser.parse_args()
    if args.sample_seconds < 1:
        parser.error("--sample-seconds must be positive")
    report = {"stations": [], "sample_seconds": args.sample_seconds}
    output = RUNTIME / "radio-recovery-verification.json"

    def record():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with SharedPowerDiagnosticClient(args.port, timeout=25) as client:
        client.hello()

        def call(service, name, **params):
            return client.call_timeout(service, name, params, timeout_ms=24000)["result"]

        def radio():
            return call("Radio", "GetState")

        def wifi():
            return call("Wifi", "GetGeneralState")

        def disconnect():
            call("Wifi", "TriggerGeneralAction", Action="Disconnect")
            wait_for(wifi, lambda state: state not in ("Connected", "Connecting"), 15, "Wi-Fi did not disconnect")

        def reconnect():
            if wifi() != "Connected":
                call("Wifi", "TriggerGeneralAction", Action="Connect")
                wait_for(wifi, lambda state: state == "Connected", 25, "Wi-Fi did not reconnect")

        def play(station):
            call("Radio", "Play", Station=station)
            def playing(s):
                if s["state"] == "Error":
                    raise RuntimeError(f'{s["error"]} (HTTP {s["http_status"]}, received {s["bytes_received"]} bytes)')
                return s["state"] == "Playing" and s["bytes_written"] >= 32000
            return wait_for(radio, playing,
                            55, "Station did not produce PCM")

        assert wifi() == "Connected" and not call("ChildMode", "GetState")["enabled"]
        assert not radio()["active"]
        for service in ("Audiobook", "LocalVoice", "VoiceAssistant"):
            assert not call(service, "GetState")["active"], service
        modes = call("DeviceModes", "GetState")
        app = next(a for a in call("SystemCore", "ListApps") if a["manifest"]["id"] == "local.radio")
        try:
            call("DeviceModes", "Wake")
            call("AudioPlayback", "SetVolume", Volume=0)
            for station in args.station or STATIONS:
                row = {"id": station, "recovered": False}
                report["stations"].append(row)
                print(f"Testing Wi-Fi outage: {station}", flush=True)
                try:
                    play(station)
                    disconnect()
                    offline = wait_for(radio, lambda s: s["state"] == "Offline", 12, "Radio did not detect the outage")
                    time.sleep(8)
                    before = radio()
                    assert before["active"] and before["bytes_received"] == offline["bytes_received"]
                    assert wifi() not in ("Connecting", "Connected")
                    row["before_wifi_return"] = {key: before[key] for key in ("bytes_received", "bytes_written")}
                    joined_at = time.monotonic()
                    reconnect()
                    ip_at = time.monotonic()
                    after = wait_for(radio, lambda s: s["state"] == "Playing" and not s["network_pending"] and
                                     s["bytes_received"] > before["bytes_received"] and
                                     s["bytes_written"] >= before["bytes_written"] + 32000, 55, "Fresh audio did not resume")
                    row.update(recovered=True, wifi_return_seconds=round(ip_at-joined_at, 2),
                               resumed_after_wifi_seconds=round(time.monotonic()-ip_at, 2),
                               reconnects=after["reconnects"])
                    if station in ("suzhou-qtfm", "naps-0"):
                        began = time.monotonic()
                        while time.monotonic() - began < args.sample_seconds:
                            time.sleep(min(5, args.sample_seconds))
                            if not radio()["active"]:
                                break
                        last = radio()
                        row.update(observed_seconds=round(time.monotonic()-began, 1),
                                   pcm_seconds=round((last["bytes_written"]-after["bytes_written"])/64000, 1),
                                   pcm_starvations=last["pcm_starvations"]-after["pcm_starvations"],
                                   decode_errors=last["decode_errors"]-after["decode_errors"],
                                   ended_early=not last["active"])
                except (TimeoutError, RuntimeError, AssertionError) as exc:
                    row["error"] = str(exc)
                    detail = radio()
                    row["last_state"] = {key: detail[key] for key in (
                        "state", "error", "http_status", "bytes_received", "bytes_written", "reconnects")}
                finally:
                    call("Radio", "Stop")
                    reconnect()
                    print(json.dumps(row, ensure_ascii=False), flush=True)
                    record()

            control = next((row["id"] for row in report["stations"] if row["recovered"]), STATIONS[0])
            report["control_station"] = control
            disconnect()
            call("Radio", "Play", Station=control)
            wait_for(radio, lambda s: s["state"] == "Offline", 12, "Radio missed the long outage")
            began = time.monotonic()
            stopped = wait_for(radio, lambda s: not s["active"] and s["state"] == "Error", 40, "Outage did not stop the player")
            report["offline_timeout_seconds"] = round(time.monotonic()-began, 2)
            assert stopped["error"] == "未联网"
            reconnect()
            assert not radio()["active"]
            call("Radio", "Play", Station=control)
            report["manual_retry_after_timeout"] = radio()["active"]
            assert report["manual_retry_after_timeout"]
            call("Radio", "Stop")

            call("SystemCore", "StartApp", AppId=app["app_id"])
            disconnect()
            call("Radio", "Play", Station=control)
            wait_for(radio, lambda s: s["state"] == "Offline", 12, "Radio missed the exit-test outage")
            began = time.monotonic()
            call("SystemCore", "StopApp", AppId=app["app_id"])
            wait_for(radio, lambda s: not s["active"], 12, "Closing the app did not stop radio")
            report["exit_offline_seconds"] = round(time.monotonic()-began, 2)
            reconnect()
            assert not radio()["active"]
            report["passed"] = all(row["recovered"] for row in report["stations"])
        finally:
            try:
                call("Radio", "Stop")
                reconnect()
            finally:
                call("AudioPlayback", "SetVolume", Volume=modes["resume_volume"])
                record()
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if not report.get("passed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
