"""Tests for the /tts subcommand dispatcher.

Config-writing subcommands are checked against the persisted config; commands
that talk to the daemon are checked by capturing the request sent to a stubbed
client.send (no real daemon involved).
"""

import json

import pytest

from tts_reader import cli, client, config, transcript


@pytest.fixture
def captured_sends(monkeypatch):
    sends = []
    monkeypatch.setattr(client, "send",
                        lambda req, autostart=True: sends.append(req) or {"ok": True})
    return sends


def test_on_off_toggles_config(capsys):
    cli.main(["on"])
    assert config.load_config()["enabled"] is True
    cli.main(["off"])
    assert config.load_config()["enabled"] is False


def test_summary_full_sets_mode():
    cli.main(["full"])
    assert config.load_config()["mode"] == "full"
    cli.main(["summary"])
    assert config.load_config()["mode"] == "summary"


def test_voice_sets_prose_and_header():
    cli.main(["voice", "prose", "Alex"])
    cli.main(["voice", "header", "Samantha"])
    cfg = config.load_config()
    assert cfg["prose_voice"] == "Alex"
    assert cfg["header_voice"] == "Samantha"


def test_voice_requires_target(capsys):
    cli.main(["voice", "Alex"])
    assert "usage" in capsys.readouterr().out.lower()


def test_wpm_validates():
    cli.main(["wpm", "220"])
    assert config.load_config()["wpm"] == 220
    cli.main(["wpm", "fast"])  # invalid, ignored
    assert config.load_config()["wpm"] == 220


def test_replay_sends_replay_channel_request(monkeypatch, captured_sends):
    monkeypatch.setattr(transcript, "latest_transcript_for_cwd",
                        lambda cwd: "/fake/session.jsonl")
    cli.main(["replay"])
    assert captured_sends and captured_sends[-1]["channel"] == "replay"
    assert captured_sends[-1]["transcript_path"] == "/fake/session.jsonl"


def test_replay_without_transcript(monkeypatch, capsys):
    monkeypatch.setattr(transcript, "latest_transcript_for_cwd", lambda cwd: None)
    cli.main(["replay"])
    assert "nothing to replay" in capsys.readouterr().out.lower()


def test_stop_sends_stop_request(captured_sends):
    cli.main(["stop"])
    assert captured_sends[-1]["type"] == "stop"


def test_preview_prints_queue_without_speaking(monkeypatch, capsys):
    monkeypatch.setattr(transcript, "latest_transcript_for_cwd",
                        lambda cwd: "/fake/session.jsonl")
    monkeypatch.setattr(transcript, "read_final_text",
                        lambda *a, **k: "# Title\n\nRun build() now.\n")
    config.set_values(mode="full")
    cli.main(["preview"])
    out = capsys.readouterr().out
    assert "utterance queue" in out
    assert "[header:" in out and "Title" in out
    assert "the build function" in out


def test_unknown_subcommand(capsys):
    cli.main(["frobnicate"])
    assert "unknown subcommand" in capsys.readouterr().out.lower()


def test_no_args_prints_usage(capsys):
    cli.main([])
    assert "usage" in capsys.readouterr().out.lower()
