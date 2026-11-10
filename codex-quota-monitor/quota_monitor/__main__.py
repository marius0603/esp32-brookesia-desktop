import argparse
import json
import os
import sys
import threading
import time
from .desktop import is_codex_running
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
    parser.add_argument('--wait-for-codex', action='store_true', help='Wait up to 30 seconds for the desktop launched by the companion shortcut')
    args = parser.parse_args()
    if args.preview_only:
        from .preview import show_preview
        show_preview()
        return
    if args.wait_for_codex:
        deadline = time.monotonic() + 30
        while not is_codex_running():
            if time.monotonic() >= deadline:
                return 1
            time.sleep(0.5)
    lock = acquire_lock()
    setup_logging()
    monitor = Monitor(load_config(args.config))
    try:
        if args.once:
            # Explicit diagnostic reads do not bypass the current device request.
            if monitor.request_only:
                from .brookesia import StableUsbClient
                port = monitor.config.get('serial_port', 'auto')
                if port == 'auto':
                    from .bridge import SerialBridge
                    ports = SerialBridge(monitor.config, None, None, None, monitor.stop).candidates()
                    port = ports[0] if len(ports) == 1 else None
                if not port or not is_codex_running():
                    print('A running Codex desktop and a connected device request are required.')
                    return 1
                with StableUsbClient(port) as client:
                    client.hello()
                    request = json.loads(client.call('Storage', 'FSReadText', {'Path':'/littlefs/quota-request.json'})['result'])
                if request.get('type') != 'quota_request' or request.get('v') != 1 or request.get('active') is not True:
                    return 1
                success = monitor.poll_once(request.get('request_id'))
            else:
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
