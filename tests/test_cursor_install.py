"""Tests for merge-safe Cursor hooks.json install helper."""

import json

from tts_reader import cursor_install


def test_merge_creates_stop_hook(tmp_path):
    checkout = tmp_path / "repo"
    (checkout / "scripts" / "tts_reader").mkdir(parents=True)
    (checkout / "scripts" / "tts_reader" / "hook_cursor.py").write_text("#")
    (checkout / "scripts" / "run").write_text("#!/bin/sh\n")
    doc = cursor_install.merge_cursor_hooks(None, checkout)
    assert doc["version"] == 1
    stop = doc["hooks"]["stop"]
    assert len(stop) == 1
    assert "hook_cursor.py" in stop[0]["command"]
    assert str(checkout.resolve()) in stop[0]["command"]
    assert stop[0]["timeout"] == 10


def test_merge_preserves_other_hooks_and_replaces_ours(tmp_path):
    checkout = tmp_path / "repo"
    (checkout / "scripts" / "tts_reader").mkdir(parents=True)
    (checkout / "scripts" / "tts_reader" / "hook_cursor.py").write_text("#")
    (checkout / "scripts" / "run").write_text("#!/bin/sh\n")
    existing = {
        "version": 1,
        "hooks": {
            "stop": [
                {"command": "/other/hook.sh", "timeout": 5},
                {
                    "command": "/old/scripts/run /old/scripts/tts_reader/hook_cursor.py",
                    "timeout": 10,
                },
            ],
            "beforeSubmitPrompt": [{"command": "echo hi"}],
        },
    }
    doc = cursor_install.merge_cursor_hooks(existing, checkout)
    stop = doc["hooks"]["stop"]
    assert len(stop) == 2
    assert stop[0]["command"] == "/other/hook.sh"
    assert "hook_cursor.py" in stop[1]["command"]
    assert "/old/" not in stop[1]["command"]
    assert doc["hooks"]["beforeSubmitPrompt"] == [{"command": "echo hi"}]


def test_install_writes_file(tmp_path):
    checkout = tmp_path / "repo"
    (checkout / "scripts" / "tts_reader").mkdir(parents=True)
    (checkout / "scripts" / "tts_reader" / "hook_cursor.py").write_text("#")
    (checkout / "scripts" / "run").write_text("#!/bin/sh\n")
    dest = tmp_path / "cursor-config" / "hooks.json"
    path, cmd = cursor_install.install(checkout, dest)
    assert path == dest
    data = json.loads(dest.read_text())
    assert data["hooks"]["stop"][0]["command"] == cmd
