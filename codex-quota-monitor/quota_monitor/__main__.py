import argparse
import json
import os
import sys
import threading
from .service import Monitor, ROOT, load_config, setup_logging


def acquire_lock():
    # Windows byte-range locks are released by the OS even after a crash.
    import msvcrt
    (ROOT / "runtime").mkdir(exist_ok=True)
    handle = (ROOT / "runtime/monitor.lock").open("a+b")
    handle.seek(0)
    if os.fstat(handle.fileno()).st_size == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        raise SystemExit("Quota monitor is already running. Use preview.ps1 to view it.")
    (ROOT / "runtime/monitor.pid").write_text(str(os.getpid()), encoding="ascii")
    (ROOT / "runtime/stop.request").unlink(missing_ok=True)
    return handle


def main():
    parser = argparse.ArgumentParser(description="Codex quota monitor")
    parser.add_argument("--once", action="store_true", help="Read real quota once, write sanitized latest.json and exit")
    parser.add_argument("--preview", action="store_true", help="Show live 480x480 preview alongside the bridge")
    parser.add_argument("--preview-only", action="store_true", help="View an existing bridge without starting another")
    parser.add_argument("--config")
    args = parser.parse_args()
    if args.preview_only:
        from .preview import show_preview
        show_preview()
        return
    lock = acquire_lock()
    setup_logging()
    monitor = Monitor(load_config(args.config))
    try:
        if args.once:
            success = monitor.poll_once()
            print(json.dumps(monitor.get_snapshot(), ensure_ascii=False))
            if monitor.client:
                monitor.client.close()
            return 0 if success else 1
        monitor.start()
        if args.preview:
            from .preview import show_preview
            show_preview(monitor)
        else:
            while not monitor.stop.wait(1):
                pass
    except KeyboardInterrupt:
        pass
    finally:
        monitor.close()
        lock.close()
        (ROOT / "runtime/monitor.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
