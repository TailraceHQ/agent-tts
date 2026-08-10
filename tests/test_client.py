"""Integration tests for the loopback-TCP control channel + auth token.

Starts a real daemon (its ``serve`` loop) on an ephemeral port and drives it
through the client, exercising the port-file handshake and token check without
any real audio (ping/status never speak).
"""

import json
import socket
import threading
import time

import pytest

from tts_reader import client
from tts_reader import daemon as D


@pytest.fixture
def running_daemon():
    d = D.Daemon()
    t = threading.Thread(target=d.serve, daemon=True)
    t.start()
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if client._read_endpoint() is not None:
            break
        time.sleep(0.02)
    else:
        raise RuntimeError("daemon did not publish its port")
    yield d
    with d.cv:
        d.running = False
        d._kill_active_locked()
        d.cv.notify_all()
    t.join(timeout=2.0)


def test_port_file_has_port_and_token(running_daemon):
    port, token = client._read_endpoint()
    assert isinstance(port, int) and port > 0
    assert token and len(token) >= 16


def test_ping_round_trip_with_token(running_daemon):
    assert client.send({"type": "ping"}, autostart=False) == {"ok": True}


def test_status_round_trip(running_daemon):
    resp = client.send({"type": "status"}, autostart=False)
    assert resp["ok"] is True and "queued" in resp


def test_request_without_token_is_rejected(running_daemon):
    port, _token = client._read_endpoint()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(("127.0.0.1", port))
    with s:
        s.sendall((json.dumps({"type": "ping"}) + "\n").encode("utf-8"))
        resp = json.loads(s.recv(65536).decode("utf-8").strip())
    assert resp["ok"] is False and resp["error"] == "unauthorized"


def test_request_with_wrong_token_is_rejected(running_daemon):
    port, _token = client._read_endpoint()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(("127.0.0.1", port))
    with s:
        req = {"type": "ping", "token": "not-the-real-token"}
        s.sendall((json.dumps(req) + "\n").encode("utf-8"))
        resp = json.loads(s.recv(65536).decode("utf-8").strip())
    assert resp["ok"] is False and resp["error"] == "unauthorized"
