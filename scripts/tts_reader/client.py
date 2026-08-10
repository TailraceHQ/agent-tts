"""Talk to the player daemon over its loopback TCP socket, autostarting it.

The control channel is ``127.0.0.1:<port>`` (not a Unix-domain socket) so the
same code runs on Windows. The daemon publishes its port and an auth token in
``config.port_path()``; every request carries the token.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_reader import config  # noqa: E402


def _read_endpoint() -> Optional[Tuple[int, str]]:
    """Return ``(port, token)`` published by the daemon, or ``None``."""
    p = config.port_path()
    if not p.exists():
        return None
    try:
        lines = p.read_text().splitlines()
        return int(lines[0]), lines[1]
    except (OSError, ValueError, IndexError):
        return None


def _connect() -> Optional[Tuple[socket.socket, str]]:
    ep = _read_endpoint()
    if ep is None:
        return None
    port, token = ep
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(("127.0.0.1", port))
        return s, token
    except OSError:
        return None


def _spawn_daemon() -> None:
    daemon_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daemon.py")
    log = open(config.log_path(), "a")
    # Detach so the daemon survives the hook/CLI process exiting. The flags for
    # that differ by OS: POSIX uses a new session, Windows a detached group.
    kwargs = dict(stdout=log, stderr=log, stdin=subprocess.DEVNULL, close_fds=True)
    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([sys.executable, daemon_py], **kwargs)


def ensure_daemon(timeout: float = 5.0) -> bool:
    conn = _connect()
    if conn is not None:
        conn[0].close()
        return True
    _spawn_daemon()
    deadline = time.time() + timeout
    while time.time() < deadline:
        conn = _connect()
        if conn is not None:
            conn[0].close()
            return True
        time.sleep(0.1)
    return False


def send(req: dict, autostart: bool = True) -> Optional[dict]:
    conn = _connect()
    if conn is None:
        if not autostart or not ensure_daemon():
            return None
        conn = _connect()
        if conn is None:
            return None
    s, token = conn
    req = dict(req, token=token)
    with s:
        try:
            s.sendall((json.dumps(req) + "\n").encode("utf-8"))
            data = s.recv(65536).decode("utf-8").strip()
            return json.loads(data) if data else None
        except (OSError, ValueError):
            return None
