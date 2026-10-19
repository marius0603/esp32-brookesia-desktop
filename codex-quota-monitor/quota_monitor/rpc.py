"""Small stdio JSON-RPC client. It never starts a chat or requests model inference."""
import glob
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path


class RpcError(RuntimeError):
    pass


def find_codex(configured=""):
    if configured:
        if not Path(configured).is_file():
            raise FileNotFoundError("configured_codex_missing")
        return configured
    found = shutil.which("codex.exe") or shutil.which("codex")
    if found:
        return found
    candidates = glob.glob(str(Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI/Codex/bin/*/codex.exe"))
    if candidates:
        return max(candidates, key=os.path.getmtime)
    raise FileNotFoundError("codex_not_found")


class CodexClient:
    def __init__(self, executable="", timeout=30):
        self.timeout = timeout
        self.sequence = 0
        self.messages = queue.Queue()
        self.process = subprocess.Popen(
            [find_codex(executable), "app-server", "--stdio"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            encoding="utf-8", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.call("initialize", {"clientInfo": {"name": "codex_quota_monitor", "title": "Codex Quota Monitor", "version": "0.1.0"}})
            self._send({"method": "initialized"})
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except json.JSONDecodeError:
                    continue
        finally:
            self.messages.put(None)

    def _send(self, packet):
        self.process.stdin.write(json.dumps(packet) + "\n")
        self.process.stdin.flush()

    def call(self, method, params=None):
        self.sequence += 1
        request_id = self.sequence
        packet = {"id": request_id, "method": method}
        if params is not None:
            packet["params"] = params
        self._send(packet)
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("rpc_timeout")
            try:
                reply = self.messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError("rpc_timeout") from exc
            if reply is None:
                raise RpcError("rpc_closed")
            if reply.get("id") == request_id:
                if "error" in reply:
                    # Only expose the RPC code, not upstream text that might contain account details.
                    raise RpcError(f"rpc_error_{reply['error'].get('code', 'unknown')}")
                return reply.get("result", {})
            if "id" in reply and "method" in reply:
                self._send({"id": reply["id"], "error": {"code": -32601, "message": "Unsupported by read-only quota monitor"}})

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        for stream in (self.process.stdin, self.process.stdout):
            if stream:
                stream.close()

    def read_quota(self):
        account = self.call("account/read", {"refreshToken": False}).get("account") or {}
        if account.get("type") not in ("chatgpt", "chatgptAuthTokens"):
            raise RpcError("auth_required")
        return self.call("account/rateLimits/read")
