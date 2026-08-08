"""Talk to the player daemon over its Unix socket, autostarting it if needed."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_reader import config  # noqa: E402


def _connect() -> Optional[socket.socket]:
    sock_path = config.socket_path()
    if not sock_path.exists():
        return None
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(str(sock_path))
        return s
    except OSError:
        return None


def _spawn_daemon() -> None:
    daemon_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daemon.py")
    log = open(config.log_path(), "a")
    subprocess.Popen(
        [sys.executable, daemon_py],
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # detach so it survives the hook/CLI exit
        close_fds=True,
    )


def ensure_daemon(timeout: float = 5.0) -> bool:
    if _connect() is not None:
        return True
    _spawn_daemon()
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = _connect()
        if s is not None:
            s.close()
            return True
        time.sleep(0.1)
    return False


def send(req: dict, autostart: bool = True) -> Optional[dict]:
    s = _connect()
    if s is None:
        if not autostart or not ensure_daemon():
            return None
        s = _connect()
        if s is None:
            return None
    with s:
        try:
            s.sendall((json.dumps(req) + "\n").encode("utf-8"))
            data = s.recv(65536).decode("utf-8").strip()
            return json.loads(data) if data else None
        except (OSError, ValueError):
            return None
