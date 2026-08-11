"""Tests for host Stop-payload → SpeakRequest adapters."""

from tts_reader.adapters import antigravity, claude, cursor
from tts_reader.adapters.common import SpeakRequest


def test_claude_from_stop_payload():
    req = claude.from_stop_payload(
        {
            "session_id": "abc",
            "transcript_path": "/proj/session.jsonl",
            "cwd": "/proj",
            "hook_event_name": "Stop",
        },
        mode="full",
        channel="auto",
    )
    assert req == SpeakRequest(
        session_id="abc",
        transcript_path="/proj/session.jsonl",
        text=None,
        cwd="/proj",
        channel="auto",
        mode="full",
    )
    daemon_req = req.to_daemon_req()
    assert daemon_req["type"] == "speak"
    assert "text" not in daemon_req  # Claude path does not embed response text


def test_claude_defaults_missing_fields(monkeypatch):
    monkeypatch.setattr(claude.os, "getcwd", lambda: "/fallback")
    req = claude.from_stop_payload({})
    assert req.session_id == "?"
    assert req.transcript_path == ""
    assert req.cwd == "/fallback"


def test_speak_request_includes_inline_text_when_set():
    req = SpeakRequest(
        session_id="s",
        transcript_path="",
        text="Hello from host",
        cwd="/w",
        mode="summary",
    )
    assert req.to_daemon_req()["text"] == "Hello from host"


def test_cursor_maps_documented_fields():
    req = cursor.from_stop_payload(
        {
            "conversation_id": "c1",
            "transcript_path": "/cursor/t.jsonl",
            "workspace_roots": ["/ws/a", "/ws/b"],
            "status": "completed",
            "hook_event_name": "stop",
        },
        mode="summary",
    )
    assert req.session_id == "c1"
    assert req.transcript_path == "/cursor/t.jsonl"
    assert req.cwd == "/ws/a"


def test_cursor_cwd_falls_back_to_getcwd(monkeypatch):
    monkeypatch.setattr(cursor.os, "getcwd", lambda: "/cwd")
    req = cursor.from_stop_payload({"conversation_id": "c", "workspace_roots": []})
    assert req.cwd == "/cwd"


def test_cursor_should_speak_only_when_completed():
    assert cursor.should_speak({"status": "completed"}) is True
    assert cursor.should_speak({"status": "aborted"}) is False
    assert cursor.should_speak({"status": "error"}) is False
    assert cursor.should_speak({}) is False


def test_antigravity_maps_documented_fields():
    req = antigravity.from_stop_payload(
        {
            "conversationId": "ag1",
            "transcriptPath": "/ag/t.jsonl",
            "workspacePaths": ["/home/proj"],
            "fullyIdle": True,
            "terminationReason": "completed",
        }
    )
    assert req.session_id == "ag1"
    assert req.transcript_path == "/ag/t.jsonl"
    assert req.cwd == "/home/proj"


def test_antigravity_should_speak_requires_fully_idle():
    assert antigravity.should_speak({
        "fullyIdle": True,
        "terminationReason": "NO_TOOL_CALL",
    }) is True
    assert antigravity.should_speak({
        "fullyIdle": False,
        "terminationReason": "NO_TOOL_CALL",
    }) is False
    assert antigravity.should_speak({"fullyIdle": True}) is True


def test_antigravity_should_speak_skips_error_terminations():
    assert antigravity.should_speak({
        "fullyIdle": True,
        "terminationReason": "error",
    }) is False
    assert antigravity.should_speak({
        "fullyIdle": True,
        "terminationReason": "max_steps_exceeded",
    }) is False
    assert antigravity.should_speak({
        "fullyIdle": True,
        "terminationReason": "NO_TOOL_CALL",
        "error": "boom",
    }) is False
    assert antigravity.should_speak({
        "fullyIdle": True,
        "terminationReason": "NO_TOOL_CALL",
        "error": "",
    }) is True
