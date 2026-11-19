"""Exercise disposable media and text fixtures on the attached device."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import time
import wave
import zipfile

from maintenance_client import SharedPowerDiagnosticClient
from verify_sd_app_storage import package

RUNTIME = Path(__file__).resolve().parents[1] / "runtime" / "sd-fault-check"
APP_ID = "local.sd.faultprobe"
APP = f"/sdcard/apps/{APP_ID}"
AUDIO = "/sdcard/audiobooks/.storage-check"
FLASH = "/littlefs/sd-faultprobe"
BOOK = f"{FLASH}/bookmark.json"
PRIVATE_DATA = f"{APP}/data/player.json"
MARKER = "sd-faultprobe-owned"
OLD = '{"path":"fixture.wav","position":17}'
NEW = '{"path":"fixture.wav","position":29}'


def corrupt_package():
    raw = bytearray(package("1.0.1", app_id=APP_ID))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        header = archive.getinfo("app/main.js").header_offset
    name_len, extra_len = struct.unpack_from("<HH", raw, header + 26)
    payload = header + 30 + name_len + extra_len
    raw[payload] |= 7  # Invalid DEFLATE block type, with a valid ZIP directory.
    return raw


def media():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0" * (16000 * 2 * 6))
    return buffer.getvalue()


def wait_until(read, predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        state = read()
        if predicate(state):
            return state
        time.sleep(.15)
    raise TimeoutError("Device did not reach expected state")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM5")
    parser.add_argument("phase", choices=("prepare", "verify", "cleanup"))
    args = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    report_file = RUNTIME / "report.json"
    report = json.loads(report_file.read_bytes()) if report_file.exists() else {}

    def save_report():
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with SharedPowerDiagnosticClient(args.port, timeout=24) as client:
        client.hello()

        def call(service, method, **params):
            return client.call_timeout(service, method, params)["result"]

        def fs(method, path, **params):
            return call("Storage", method, Path=path, **params)

        def exists(path):
            return fs("FSStat", path)["exists"]

        def put(path, text):
            return fs("FSWriteText", path, Data=text)

        def read(path):
            return fs("FSReadText", path)

        def player():
            return call("Audiobook", "GetState")

        def install(data):
            path = RUNTIME / "fixture.bpk"
            path.write_bytes(data)
            return client.transfer("install_bpk", path, None, True)

        def upload(name, data):
            path = RUNTIME / name
            path.write_bytes(data)
            remote = f"sd-faultprobe-{time.time_ns()}.bin"
            uploaded = client.transfer("put", path, "sd-themes/" + remote, False)
            assert uploaded["ok"] and uploaded["sha256"] == hashlib.sha256(data).hexdigest()
            transient = "/sdcard/themes/" + remote
            try:
                call("Storage", "FSCopyTree", From=transient, To=f"{AUDIO}/{name}", Overwrite=False)
            finally:
                fs("FSRemove", transient)

        if args.phase == "prepare":
            assert not any(exists(path) for path in (APP, AUDIO, FLASH)), "Existing diagnostics must be cleaned first"
            modes = call("DeviceModes", "GetState")
            assert not call("ChildMode", "GetState")["enabled"]
            assert not modes["screen_locked"] and not player()["sleep_active"]
            assert all(not call(service, "GetState")["active"] for service in ("Audiobook", "Radio", "LocalVoice", "VoiceAssistant"))
            fs("FSMkdir", FLASH)
            put(f"{FLASH}/owner", MARKER)
            report = {"owned": True, "prepared": False}
            save_report()
            assert install(package("1.0.0", app_id=APP_ID))["ok"]
            put(f"{APP}/data/owner", MARKER)
            put(BOOK, OLD)
            put(PRIVATE_DATA, OLD)
            put(PRIVATE_DATA, NEW)
            assert read(PRIVATE_DATA) == NEW
            put(PRIVATE_DATA, OLD)
            digest = call("SdResources", "InspectTree", Path=APP)
            for label, data in (("corrupt_bpk", corrupt_package()),
                                ("capacity_preflight", package("1.0.1", oversize=True, app_id=APP_ID))):
                try:
                    install(data)
                except RuntimeError as error:
                    if label == "capacity_preflight":
                        assert "Insufficient install space" in str(error), str(error)
                else:
                    raise AssertionError(f"{label} was accepted")
                assert call("SdResources", "InspectTree", Path=APP) == digest
                report[label] = True
            # Refuse a blocked staging path and leave the previously saved value.
            fs("FSMkdir", PRIVATE_DATA + ".~stage")
            try:
                try:
                    put(PRIVATE_DATA, NEW)
                except RuntimeError as error:
                    assert "Invalid text update path" in str(error), str(error)
                else:
                    raise AssertionError("Blocked staging unexpectedly succeeded")
                assert read(PRIVATE_DATA) == OLD
                report["staging_failure_preserved_text"] = True
            finally:
                fs("FSRemove", PRIVATE_DATA + ".~stage")

            fs("FSMkdir", AUDIO)
            put(f"{AUDIO}/owner", MARKER)
            upload("damaged.wav", b"broken RIFF header")
            upload("healthy.wav", media())
            try:
                call("DeviceModes", "Wake")
                call("AudioPlayback", "SetVolume", Volume=0)
                call("Audiobook", "Play", Path=f"{AUDIO}/damaged.wav", Position=0)
                bad = wait_until(player, lambda s: not s["active"])
                assert bad["state"] == "Error" and bad["bytes_written"] == 0
                report["damaged_media_rejected"] = True
                call("Audiobook", "TestReadFailure", Enabled=True)
                call("Audiobook", "Play", Path=f"{AUDIO}/healthy.wav", Position=0)
                call("Audiobook", "SetSleepTimer", Minutes=15)
                failed = wait_until(player, lambda s: not s["active"])
                assert failed["state"] == "Error" and failed["error"] == "无法读取 SD 卡音频", failed
                assert failed["bytes_written"] >= 64000 and not failed["sleep_active"]
                report["mid_playback_read_fault"] = True
                call("Audiobook", "Play", Path=f"{AUDIO}/healthy.wav", Position=0)
                ended = wait_until(player, lambda s: not s["active"])
                assert ended["state"] == "Ended" and ended["bytes_written"] >= 350000, ended
                report["healthy_play_and_eof"] = True
            finally:
                call("Audiobook", "TestReadFailure", Enabled=False)
                call("Audiobook", "Stop")
                call("AudioPlayback", "SetVolume", Volume=modes["resume_volume"])

            # Reproduce the directory states left at two interrupted commit stages.
            put(BOOK + ".~stage", '{"partial":')
            call("Storage", "FSRename", From=PRIVATE_DATA, To=PRIVATE_DATA + ".~previous")
            put(PRIVATE_DATA + ".~stage", '{"partial":')
            assert not exists(PRIVATE_DATA)
            report["prepared"] = True
            save_report()
            print("Fixtures prepared. Reset the board, then run verify.", flush=True)
        else:
            assert report.get("owned") and read(f"{FLASH}/owner") == MARKER
            if args.phase == "verify":
                assert report.get("prepared")
                assert not exists(PRIVATE_DATA)
                assert read(BOOK) == OLD and read(PRIVATE_DATA) == OLD
                for path in (BOOK, PRIVATE_DATA):
                    put(path, NEW)
                    assert read(path) == NEW and not any(exists(path + suffix) for suffix in (".~stage", ".~previous"))
                report["interrupted_text_update_recovered_after_reset"] = True
                save_report()
            else:
                for path in (AUDIO, APP):
                    if exists(path):
                        owner = f"{path}/data/owner" if path == APP else f"{path}/owner"
                        assert read(owner) == MARKER
                        fs("FSRemove", path)
                fs("FSRemove", FLASH)
                report["cleaned"] = True
                save_report()
            print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
