"""Tests for the Stop-hook entrypoint.

The hook must: stay silent when disabled, and when enabled send an AUTO speak
request carrying the transcript path (it must NOT read or embed the response
text itself).
"""

import io
import json

import pytest

from tts_reader import client, config
from tts_reader import hook


PAYLOAD = {
    "session_id": "abc",
    "transcript_path": "/proj/session.jsonl",
    "cwd": "/proj",
    "hook_event_name": "Stop",
}


@pytest.fixture
def captured_sends(monkeypatch):
    sends = []
    monkeypatch.setattr(client, "send", lambda req: sends.append(req) or {"ok": True})
    return sends


def _feed(monkeypatch, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))


def test_noop_when_disabled(monkeypatch, captured_sends):
    config.set_values(enabled=False)
    _feed(monkeypatch, PAYLOAD)
    hook.main()
    assert captured_sends == []


def test_signals_daemon_when_enabled(monkeypatch, captured_sends):
    config.set_values(enabled=True, mode="summary")
    _feed(monkeypatch, PAYLOAD)
    hook.main()
    assert len(captured_sends) == 1
    req = captured_sends[0]
    assert req["type"] == "speak"
    assert req["channel"] == "auto"
    assert req["session_id"] == "abc"
    assert req["transcript_path"] == "/proj/session.jsonl"
    assert req["mode"] == "summary"
    # the hook must not embed any response text
    assert "text" not in req


def test_bad_stdin_is_swallowed(monkeypatch, captured_sends):
    config.set_values(enabled=True)
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    hook.main()  # must not raise
    assert captured_sends == []


def test_skips_when_turn_was_a_tts_command_echo(monkeypatch, captured_sends):
    """Regression test: the Stop hook fires right after a /tts command's own
    relay turn too (e.g. "Replaying last response."). That text is plugin
    meta-output, not a real Claude answer, and auto-speaking it on top of
    /tts replay's own audio is what made a single replay play multiple times.
    """
    config.set_values(enabled=True)
    config.mark_command_run()  # simulates cli.py having just run a command
    _feed(monkeypatch, PAYLOAD)
    hook.main()
    assert captured_sends == []


def test_suppression_is_single_use(monkeypatch, captured_sends):
    config.set_values(enabled=True)
    config.mark_command_run()
    _feed(monkeypatch, PAYLOAD)
    hook.main()  # consumes the marker, stays silent
    _feed(monkeypatch, PAYLOAD)
    hook.main()  # a real turn's Stop event - must not still be suppressed
    assert len(captured_sends) == 1
