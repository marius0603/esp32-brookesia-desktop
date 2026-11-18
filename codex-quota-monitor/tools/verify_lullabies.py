"""Verify collection playback on the device without confusing MP3 seek time with EOF."""
import argparse
import json
from pathlib import Path
import time

from deploy_clock_widgets import tree_hash
from deploy_lullabies import package
from maintenance_client import SharedPowerDiagnosticClient
from verify_audio_soak import HostAwake


ROOT = Path(__file__).resolve().parents[2]
SONG_APP = "local.nurserysongs"
SONG_ROOT = f"/sdcard/apps/{SONG_APP}"
PLAYER_DATA = (
    f"{SONG_ROOT}/data/player.json",
    f"{SONG_ROOT}/data/play-mode.json",
    "/littlefs/audiobook-bookmark.json",
    "/littlefs/audiobook-play-mode.json",
)
LEGACY_TIMEOUT_SECONDS = 22


class PlaybackCheck:
    def __init__(self, call, report):
        self.call = call
        self.report = report

    def audio(self, name, **params):
        return self.call("Audiobook", name, **params)

    def read(self):
        state = self.audio("GetState")
        if state["error"]:
            raise AssertionError(f"Playback error: {state['error']}")
        return state

    def wait(self, condition, timeout, label, interval=.35):
        deadline = time.monotonic() + timeout
        while True:
            state = self.read()
            if condition(state):
                return state
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"{label}: timed out in {state['state']} at {state['position']}s "
                    f"of {state['duration']}s, {state['bytes_written']} PCM bytes"
                )
            time.sleep(interval)

    @staticmethod
    def playing(state, path):
        return state["state"] == "Playing" and state["active"] and state["path"] == path

    def play(self, path):
        self.audio("Play", Path=path, Position=0)
        return self.wait(
            lambda s: self.playing(s, path) and s["bytes_written"] >= 65536 and s["duration"] > 0,
            35, "start playback",
        )

    def record(self, label, **evidence):
        self.report["checks"].append({"check": label, **evidence})
        print(json.dumps(self.report["checks"][-1], ensure_ascii=False), flush=True)

    def verify_decodes(self, tracks, durations):
        for track in tracks:
            state = self.play(track["path"])
            assert abs(state["duration"] - durations[track["path"]]) < 2
            self.report["decodes"].append(
                {"title": track["title"], "duration": state["duration"], "bytes_written": state["bytes_written"]}
            )
        self.record("ten_original_mp3_files_decode")

    def advance(self, first, allowed, label, *, seek=False, legacy=False):
        initial = self.play(first)
        duration = initial["duration"]
        cutoff = duration - (1 if legacy else 3)
        began = time.monotonic()
        if seek:
            self.audio("Seek", Seconds=cutoff)
        transition = {}
        def advanced(state):
            elapsed = time.monotonic() - began
            if state["path"] == first:
                if state["position"] >= cutoff:
                    transition.setdefault("tail_observed_at_seconds", round(elapsed, 2))
                if not seek:
                    assert state["pcm_starvations"] == 0, "Natural playback starved"
                return False
            if state["active"] or state["path"]:
                assert state["path"] in allowed, f"{label}: wrong successor {state['path']}"
            return state["state"] == "Playing" and state["active"] and state["bytes_written"] > 0

        # The current MP3 decoder may decode from the beginning to seek. Time
        # that separately and allow the player a short deadline once at the tail.
        hit = self.wait(advanced, duration + 35, label)
        elapsed = round(time.monotonic() - began, 2)
        assert "tail_observed_at_seconds" in transition, f"{label}: never observed the outgoing track tail"
        after_tail = round(elapsed - transition["tail_observed_at_seconds"], 2)
        assert after_tail <= (5 if legacy else 9), f"{label}: delayed after reaching the tail"
        evidence = dict(method="seek" if seek else "natural", elapsed_seconds=elapsed,
                        seconds_after_tail=after_tail, successor=Path(hit["path"]).name, **transition)
        if legacy:
            evidence["would_timeout_at_previous_22_seconds"] = elapsed > LEGACY_TIMEOUT_SECONDS
        self.record(label, **evidence)

    def holds_stopped(self, terminal, seconds, label):
        began = time.monotonic()
        initial = self.read()
        def stopped(state):
            assert state["state"] == terminal and not state["active"], f"{label}: playback restarted"
            assert state["path"] == initial["path"] and state["bytes_written"] == initial["bytes_written"]
            return time.monotonic() - began >= seconds
        self.wait(stopped, seconds + 3, label, interval=.7)

    def sequence_boundary(self, track, label):
        initial = self.play(track)
        self.audio("Seek", Seconds=initial["duration"] - 3)
        def terminal(state):
            assert state["path"] == track, f"{label}: playback crossed the collection boundary"
            return state["state"] == "Ended" and not state["active"]
        self.wait(terminal, initial["duration"] + 35, label)
        self.holds_stopped("Ended", 5, label)
        self.record(label, stopped_at=Path(track).name)

    def repeat(self, track):
        initial = self.play(track)
        duration = initial["duration"]
        saw_tail = False
        self.audio("Seek", Seconds=duration - 3)
        def restarted(state):
            nonlocal saw_tail
            assert state["path"] == track, "Repeat-one changed tracks"
            saw_tail |= state["position"] >= duration - 3
            return saw_tail and self.playing(state, track) and state["position"] < 3 and state["bytes_written"] > 0
        self.wait(restarted, duration + 35, "repeat one")
        self.record("single_repeat_restarts_same_track")

    def sleep(self, real_minutes):
        original_count = self.read()["goodnight_count"]
        if real_minutes:
            self.audio("SetSleepTimer", Minutes=real_minutes)
        else:
            self.audio("TestSleepTimer")
        min_gain = 1000
        def ended(state):
            nonlocal min_gain
            if state["sleep_fading"]:
                min_gain = min(min_gain, state["sleep_gain_per_mille"])
            return state["state"] == "SleepEnded" and state["sleep_completed"] and not state["active"]
        state = self.wait(ended, (real_minutes * 60 if real_minutes else 10) + 25, "sleep timer", interval=.55)
        assert min_gain < 1000, "Sleep fade was not observed"
        assert not state["sleep_active"] and state["goodnight_count"] == original_count + 1
        self.holds_stopped("SleepEnded", 30, "stay stopped after sleep")
        self.record("sleep_fade_goodnight_and_hold", timer_seconds=real_minutes * 60 or 10,
                    minimum_gain_per_mille=min_gain, verified_stopped_seconds=30)


def verify_library(call, manifest, version):
    stories = call("Audiobook", "List")["tracks"]
    songs = call("Audiobook", "ListSongs")["tracks"]
    durations = {f"{manifest['device_root']}/{song['filename']}": song["duration_seconds"]
                 for song in manifest["songs"]}
    lullabies = [t for t in songs if t["path"] in durations]
    nursery = [t for t in songs if not t["path"].startswith(manifest["device_root"] + "/")]
    assert len(stories) == 30 and len(nursery) == 20 and len(lullabies) == len(durations) == 10 and len(songs) == 30
    assert not {t["path"] for t in songs} & {t["path"] for t in stories}
    files = package(version)
    for folder in ("app", "res"):
        subset = {name[len(folder)+1:]: data for name, data in files.items() if name.startswith(folder+"/")}
        actual = call("SdResources", "InspectTree", Path=f"{SONG_ROOT}/{folder}")["sha256"]
        assert actual == tree_hash(subset), f"Installed {folder} differs from the released package"
    return stories, songs, nursery, lullabies, durations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM5")
    parser.add_argument("--real-sleep", action="store_true", help="Use the normal 15-minute timer")
    args = parser.parse_args()
    releases = json.loads((ROOT / "versions.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "samples/songs/lullabies-20261109.json").read_text(encoding="utf-8"))
    folder = ROOT / "codex-quota-monitor/runtime" / f"lullaby-verify-{time.time_ns()}"
    folder.mkdir(parents=True)
    report = {"passed": False, "checks": [], "decodes": []}

    with HostAwake(), SharedPowerDiagnosticClient(args.port, timeout=35) as client:
        client.hello()
        def call(service, name, **params):
            return client.call_timeout(service, name, params)["result"]
        check = PlaybackCheck(call, report)
        before = call("DeviceModes", "GetState")
        playback = check.read()
        assert not call("ChildMode", "GetState")["enabled"] and not before["screen_locked"]
        assert not playback["sleep_active"] and not any(
            call(s, "GetState")["active"] for s in ("Audiobook", "Radio", "VoiceAssistant", "LocalVoice", "LearningAudio")
        ), "Finish active audio and any sleep timer before testing"
        assert before["firmware_version"] == releases["firmware"]
        apps = call("SystemCore", "ListApps")
        player = next(a for a in apps if a["manifest"]["id"] == SONG_APP)
        version = player["manifest"]["version"]
        assert version == releases["apps"][SONG_APP]
        stories, songs, nursery, lullabies, durations = verify_library(call, manifest, version)
        original = call("SystemCore", "GetActiveApp")
        def exists(path):
            return call("Storage", "FSStat", Path=path)["exists"]
        files = {path: call("Storage", "FSReadText", Path=path) if exists(path) else None for path in PLAYER_DATA}
        recovery = {"volume": before["resume_volume"], "deep_sleep": before["auto_deep_sleep_minutes"],
                    "song_mode": playback["song_play_mode"], "speed": playback["speed"], "files": files, "app": original}
        (folder / "recovery.json").write_text(json.dumps(recovery, ensure_ascii=False, indent=2), encoding="utf-8")
        report.update(firmware=before["firmware_version"], version=version, apps=len(apps))
        result = folder / "result.json"
        try:
            check.record("verified_release_catalog_and_sd_resources", stories=30, nursery=20, lullabies=10)
            call("DeviceModes", "Wake")
            call("DeviceModes", "SetAutoDeepSleep", Minutes=0)
            call("AudioPlayback", "SetVolume", Volume=0)
            call("SystemCore", "StartApp", AppId=player["app_id"])
            active = call("SystemCore", "GetActiveApp")
            assert active["app_id"] == player["app_id"] and active["state"] == "Running" and not active["last_error"]
            check.audio("SetSpeed", Speed=1)
            tracks = [t["path"] for t in lullabies]
            check.audio("SetSongMode", Mode="sequence")
            longest = max(range(len(tracks)), key=lambda i: durations[tracks[i]])
            assert longest < len(tracks) - 1
            check.advance(tracks[longest], {tracks[longest+1]}, "legacy_seek_window", seek=True, legacy=True)
            check.verify_decodes(lullabies, durations)
            check.advance(tracks[0], {tracks[1]}, "sequence_natural_eof_from_start")
            check.sequence_boundary(tracks[-1], "lullaby_last_track_stops")
            check.sequence_boundary(nursery[-1]["path"], "nursery_last_track_stops")
            check.audio("SetSongMode", Mode="random")
            check.advance(tracks[-1], set(tracks[:-1]), "random_stays_in_lullabies_and_skips_current", seek=True)
            check.audio("SetSongMode", Mode="repeat_one")
            check.repeat(tracks[0])
            check.sleep(15 if args.real_sleep else 0)
            report["passed"] = True
        except BaseException as error:
            report["failure"] = str(error)
            raise
        finally:
            try:
                call("SystemCore", "StopApp", AppId=player["app_id"])
                check.audio("Stop")
                check.audio("SetSongMode", Mode=recovery["song_mode"])
                check.audio("SetSpeed", Speed=recovery["speed"])
                for path, data in files.items():
                    if data is not None:
                        call("Storage", "FSWriteText", Path=path, Data=data)
                        assert call("Storage", "FSReadText", Path=path) == data
                    elif exists(path):
                        call("Storage", "FSRemove", Path=path)
                        assert not exists(path)
                call("AudioPlayback", "SetVolume", Volume=recovery["volume"])
                call("DeviceModes", "SetAutoDeepSleep", Minutes=recovery["deep_sleep"])
                after = call("DeviceModes", "GetState")
                assert (after["resume_volume"], after["auto_deep_sleep_minutes"]) == (recovery["volume"], recovery["deep_sleep"])
                stopped = check.read()
                assert not stopped["active"] and not stopped["sleep_active"]
                assert (stopped["song_play_mode"], stopped["speed"]) == (recovery["song_mode"], recovery["speed"])
                assert check.audio("List")["tracks"] == stories and check.audio("ListSongs")["tracks"] == songs
                report["preferences_restored"] = True
                if original and original["app_id"] != 1:
                    call("DeviceModes", "Wake")
                    call("SystemCore", "StartApp", AppId=original["app_id"])
            except BaseException as error:
                report.update(passed=False, restore_error=str(error))
                raise
            finally:
                result.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(result, flush=True)


if __name__ == "__main__":
    main()
