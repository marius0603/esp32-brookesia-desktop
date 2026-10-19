"""Resolve developer runtimes on another computer without depending on Codex paths."""
import os
from pathlib import Path
import shutil


def find_node():
    explicit = os.environ.get('QUOTA_NODE')
    if explicit:
        return explicit
    installed = shutil.which('node')
    if installed:
        return installed
    bundled = Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    if bundled.is_file():
        return str(bundled)
    raise SystemExit('Node.js is required. Install Node.js LTS or set QUOTA_NODE to node.exe.')
