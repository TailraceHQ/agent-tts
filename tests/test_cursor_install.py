"""Tests for merge-safe Cursor hooks.json + /tts command install helper."""

import json

from tts_reader import cursor_install


def _fake_checkout(tmp_path):
    checkout = tmp_path / "repo"
    (checkout / "scripts" / "tts_reader").mkdir(parents=True)
    (checkout / "scripts" / "tts_reader" / "hook_cursor.py").write_text("#")
    (checkout / "scripts" / "run").write_text("#!/bin/sh\n")
    hosts = checkout / "hosts" / "cursor"
    (hosts / "commands").mkdir(parents=True)
    (hosts / "skills" / "tts").mkdir(parents=True)
    (hosts / "commands" / "tts.md").write_text(
        '!"REPLACE_WITH_CHECKOUT/scripts/run" $ARGUMENTS\n'
    )
    (hosts / "skills" / "tts" / "SKILL.md").write_text(
        "checkout=REPLACE_WITH_CHECKOUT\n"
    )
    return checkout


def test_merge_creates_stop_hook(tmp_path):
    checkout = _fake_checkout(tmp_path)
    doc = cursor_install.merge_cursor_hooks(None, checkout)
    assert doc["version"] == 1
    stop = doc["hooks"]["stop"]
    assert len(stop) == 1
    assert "hook_cursor.py" in stop[0]["command"]
    assert str(checkout.resolve()) in stop[0]["command"]
    assert stop[0]["timeout"] == 10


def test_merge_preserves_other_hooks_and_replaces_ours(tmp_path):
    checkout = _fake_checkout(tmp_path)
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


def test_install_writes_hooks_command_and_skill(tmp_path):
    checkout = _fake_checkout(tmp_path)
    dest = tmp_path / "cursor-config" / "hooks.json"
    commands = tmp_path / "cursor-config" / "commands"
    skills = tmp_path / "cursor-config" / "skills" / "tts"
    path, cmd, cmd_path, skill_path = cursor_install.install(
        checkout,
        dest,
        commands_dir=commands,
        skills_dir=skills,
    )
    assert path == dest
    data = json.loads(dest.read_text())
    assert data["hooks"]["stop"][0]["command"] == cmd
    assert cmd_path == commands / "tts.md"
    assert skill_path == skills / "SKILL.md"
    body = cmd_path.read_text()
    assert str(checkout.resolve()) in body
    assert "REPLACE_WITH_CHECKOUT" not in body
    assert str(checkout.resolve()) in skill_path.read_text()


def test_install_skip_commands(tmp_path):
    checkout = _fake_checkout(tmp_path)
    dest = tmp_path / "hooks.json"
    path, cmd, cmd_path, skill_path = cursor_install.install(
        checkout, dest, skip_commands=True
    )
    assert path == dest
    assert cmd
    assert cmd_path is None
    assert skill_path is None
