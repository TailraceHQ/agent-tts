"""Tests for Cursor and Antigravity Stop-hook entry points."""

import io
import json

import pytest

from tts_reader import client, config
from tts_reader import hook_antigravity, hook_cursor


CURSOR_PAYLOAD = {
    "conversation_id": "c1",
    "transcript_path": "/cursor/t.jsonl",
    "workspace_roots": ["/ws"],
    "status": "completed",
    "hook_event_name": "stop",
}

AGY_PAYLOAD = {
    "conversationId": "ag1",
    "transcriptPath": "/ag/t.jsonl",
    "workspacePaths": ["/proj"],
    "fullyIdle": True,
    "terminationReason": "NO_TOOL_CALL",
    "error": "",
}


@pytest.fixture
def captured_sends(monkeypatch):
    sends = []
    monkeypatch.setattr(client, "send", lambda req: sends.append(req) or {"ok": True})
    return sends


def _feed(monkeypatch, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))


def _stdout(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    return buf


def test_cursor_emits_empty_object_and_speaks_when_completed(
    monkeypatch, captured_sends
):
    config.set_values(enabled=True, mode="summary")
    out = _stdout(monkeypatch)
    _feed(monkeypatch, CURSOR_PAYLOAD)
    hook_cursor.main()
    assert out.getvalue() == "{}\n"
    assert len(captured_sends) == 1
    req = captured_sends[0]
    assert req["session_id"] == "c1"
    assert req["transcript_path"] == "/cursor/t.jsonl"
    assert req["cwd"] == "/ws"
    assert "followup_message" not in json.loads(out.getvalue())


def test_cursor_skips_aborted_but_still_prints_empty_object(
    monkeypatch, captured_sends
):
    config.set_values(enabled=True)
    out = _stdout(monkeypatch)
    _feed(monkeypatch, {**CURSOR_PAYLOAD, "status": "aborted"})
    hook_cursor.main()
    assert captured_sends == []
    assert out.getvalue() == "{}\n"


def test_cursor_skips_when_disabled_with_empty_stdout(monkeypatch, captured_sends):
    config.set_values(enabled=False)
    out = _stdout(monkeypatch)
    _feed(monkeypatch, CURSOR_PAYLOAD)
    hook_cursor.main()
    assert captured_sends == []
    assert out.getvalue() == "{}\n"


def test_cursor_respects_command_suppression(monkeypatch, captured_sends):
    config.set_values(enabled=True)
    config.mark_command_run()
    out = _stdout(monkeypatch)
    _feed(monkeypatch, CURSOR_PAYLOAD)
    hook_cursor.main()
    assert captured_sends == []
    assert out.getvalue() == "{}\n"


def test_antigravity_emits_empty_object_never_continue(monkeypatch, captured_sends):
    config.set_values(enabled=True)
    out = _stdout(monkeypatch)
    _feed(monkeypatch, AGY_PAYLOAD)
    hook_antigravity.main()
    body = out.getvalue()
    assert body == "{}\n"
    parsed = json.loads(body)
    assert parsed == {}
    assert "decision" not in parsed
    assert len(captured_sends) == 1
    assert captured_sends[0]["session_id"] == "ag1"
    assert captured_sends[0]["transcript_path"] == "/ag/t.jsonl"


def test_antigravity_skips_when_not_fully_idle(monkeypatch, captured_sends):
    config.set_values(enabled=True)
    out = _stdout(monkeypatch)
    _feed(monkeypatch, {**AGY_PAYLOAD, "fullyIdle": False})
    hook_antigravity.main()
    assert captured_sends == []
    assert out.getvalue() == "{}\n"


def test_antigravity_skips_error_termination(monkeypatch, captured_sends):
    config.set_values(enabled=True)
    out = _stdout(monkeypatch)
    _feed(monkeypatch, {**AGY_PAYLOAD, "terminationReason": "error"})
    hook_antigravity.main()
    assert captured_sends == []
    assert out.getvalue() == "{}\n"


def test_host_hooks_never_emit_followup_or_continue(monkeypatch, captured_sends):
    config.set_values(enabled=True)
    for mod, payload in (
        (hook_cursor, CURSOR_PAYLOAD),
        (hook_antigravity, AGY_PAYLOAD),
    ):
        out = _stdout(monkeypatch)
        _feed(monkeypatch, payload)
        mod.main()
        parsed = json.loads(out.getvalue())
        assert parsed == {}
        assert "followup_message" not in parsed
        assert parsed.get("decision") != "continue"
