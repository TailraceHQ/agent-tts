"""Tests for reading the final assistant text out of a transcript.

The important behaviors: pick the LAST assistant text block (not a tool-call
preamble), tolerate the internal/volatile JSONL format, honor freshness so we
don't read the previous turn, and locate a session's transcript by cwd.
"""

import json
import time

from tts_reader import transcript


def _write(path, entries):
    path.write_text("\n".join(json.dumps(e) for e in entries))
    return str(path)


def _assistant(text, ts):
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def _tool_use(ts):
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {"role": "assistant",
                    "content": [{"type": "tool_use", "name": "Read", "input": {}}]},
    }


def _tool_result(ts):
    return {
        "type": "user",
        "timestamp": ts,
        "message": {"role": "user",
                    "content": [{"type": "tool_result", "content": "..."}]},
    }


def test_picks_final_text_not_preamble(tmp_path):
    # A tool-using turn: preamble text, then tool_use, then the real answer.
    path = _write(tmp_path / "t.jsonl", [
        _assistant("Let me check that.", "2026-08-08T10:00:00Z"),
        _tool_use("2026-08-08T10:00:01Z"),
        _tool_result("2026-08-08T10:00:02Z"),
        _assistant("Here is the answer.", "2026-08-08T10:00:03Z"),
    ])
    assert transcript.read_final_text(path, timeout=0.2) == "Here is the answer."


def test_skips_tool_use_and_string_content(tmp_path):
    path = _write(tmp_path / "t.jsonl", [
        {"type": "assistant", "timestamp": "2026-08-08T10:00:00Z",
         "message": {"role": "assistant", "content": "plain string answer"}},
    ])
    assert transcript.read_final_text(path, timeout=0.2) == "plain string answer"


def test_ignores_corrupt_lines(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text(
        "not json\n"
        + json.dumps(_assistant("good answer", "2026-08-08T10:00:00Z"))
        + "\n{broken"
    )
    assert transcript.read_final_text(str(p), timeout=0.2) == "good answer"


def test_missing_file_returns_none():
    assert transcript.read_final_text("/no/such/file.jsonl", timeout=0.1) is None


def test_freshness_falls_back_after_timeout(tmp_path):
    # Only a definitively-old message exists; request_ts is in the future.
    path = _write(tmp_path / "t.jsonl", [
        _assistant("stale answer", "2000-01-01T00:00:00Z"),
    ])
    start = time.time()
    got = transcript.read_final_text(path, request_ts=time.time() + 1000, timeout=0.3)
    assert got == "stale answer"           # falls back to last seen
    assert time.time() - start >= 0.3      # actually waited the timeout


def test_freshness_returns_immediately_when_fresh(tmp_path):
    path = _write(tmp_path / "t.jsonl", [
        _assistant("fresh answer", "2026-08-08T10:00:00Z"),
    ])
    # request_ts well before the entry -> considered fresh, no waiting
    got = transcript.read_final_text(path, request_ts=1.0, timeout=5.0, poll=0.05)
    assert got == "fresh answer"


def test_project_dir_slug():
    d = transcript.project_dir_for_cwd("/Users/j/dev/proj")
    assert d.name == "-Users-j-dev-proj"


def test_latest_transcript_for_cwd(tmp_path, monkeypatch):
    monkeypatch.setattr(transcript, "project_dir_for_cwd", lambda cwd: tmp_path)
    old = tmp_path / "old.jsonl"
    new = tmp_path / "new.jsonl"
    old.write_text("{}")
    time.sleep(0.02)
    new.write_text("{}")
    assert transcript.latest_transcript_for_cwd("/anything") == str(new)


def test_latest_transcript_none_when_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(transcript, "project_dir_for_cwd", lambda cwd: tmp_path)
    assert transcript.latest_transcript_for_cwd("/anything") is None
