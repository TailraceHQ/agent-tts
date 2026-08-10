"""Tests for parsing `say -v ?` output (voice listing)."""

import pytest

from tts_reader import engine
from tts_reader.engine import linux as linux_backend
from tts_reader.engine import windows as windows_backend
from tts_reader.engine.cloud import CloudBackend
from tts_reader.engine.linux import LinuxBackend
from tts_reader.engine.macos import MacOSBackend
from tts_reader.engine.windows import WindowsBackend

SAMPLE = """\
Albert              en_US    # Hello! My name is Albert.
Alice               it_IT    # Ciao! Mi chiamo Alice.
Bad News            en_US    # The light you see...
Zosia               pl_PL    # Dzień dobry.
garbage line without locale
"""


def test_parse_voice_lines_basic():
    voices = engine.parse_voice_lines(SAMPLE)
    names = [v[0] for v in voices]
    assert "Albert" in names
    assert "Zosia" in names
    assert "garbage line without locale" not in names


def test_parse_voice_lines_multiword_name():
    voices = engine.parse_voice_lines(SAMPLE)
    by_name = {v[0]: v for v in voices}
    assert "Bad News" in by_name
    assert by_name["Bad News"][1] == "en_US"


def test_parse_voice_lines_locale_and_sample():
    voices = engine.parse_voice_lines(SAMPLE)
    alice = next(v for v in voices if v[0] == "Alice")
    assert alice[1] == "it_IT"
    assert alice[2].startswith("Ciao")


# -- backend factory ----------------------------------------------------------


@pytest.mark.parametrize("system,expected", [
    ("Darwin", MacOSBackend),
    ("Windows", WindowsBackend),
    ("Linux", LinuxBackend),
])
def test_auto_backend_follows_platform(monkeypatch, system, expected):
    monkeypatch.setattr(engine.platform, "system", lambda: system)
    assert isinstance(engine.get_backend({"backend": "auto"}), expected)


@pytest.mark.parametrize("choice,expected", [
    ("macos", MacOSBackend),
    ("windows", WindowsBackend),
    ("linux", LinuxBackend),
    ("cloud", CloudBackend),
])
def test_explicit_backend_wins_over_platform(monkeypatch, choice, expected):
    monkeypatch.setattr(engine.platform, "system", lambda: "Darwin")
    assert isinstance(engine.get_backend({"backend": choice}), expected)


def test_no_config_defaults_to_os_backend(monkeypatch):
    monkeypatch.setattr(engine.platform, "system", lambda: "Linux")
    assert isinstance(engine.get_backend(), LinuxBackend)


# -- wpm -> engine rate mappings ---------------------------------------------


@pytest.mark.parametrize("wpm,rate", [
    (175, 0),    # baseline
    (200, 1),
    (150, -1),
    (400, 9),
    (1000, 10),   # clamped high
    (-100, -10),  # clamped low
])
def test_wpm_to_sapi_rate(wpm, rate):
    assert windows_backend.wpm_to_sapi_rate(wpm) == rate


@pytest.mark.parametrize("wpm,rate", [
    (175, 0),
    (350, 100),   # clamped high
    (0, -100),    # clamped low
])
def test_wpm_to_spd_rate(wpm, rate):
    assert linux_backend.wpm_to_spd_rate(wpm) == rate


# -- OS backends spawn the right command (mock subprocess) --------------------


def test_macos_speak_builds_say_command(monkeypatch):
    calls = {}

    def fake_popen(cmd, **kw):
        calls["cmd"] = cmd
        return object()

    monkeypatch.setattr(engine.macos.subprocess, "Popen", fake_popen)
    MacOSBackend().speak("hi there", "Alex", 200)
    assert calls["cmd"][:5] == ["say", "-r", "200", "-v", "Alex"]
    assert calls["cmd"][-1] == "hi there"


def test_linux_prefers_espeak_and_feeds_stdin(monkeypatch):
    monkeypatch.setattr(linux_backend.shutil, "which",
                        lambda name: "/usr/bin/espeak-ng" if name == "espeak-ng" else None)
    captured = {}

    class FakeProc:
        def __init__(self):
            self.stdin = self

        def write(self, b):
            captured["text"] = b

        def close(self):
            captured["closed"] = True

    def fake_popen(cmd, **kw):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(linux_backend.subprocess, "Popen", fake_popen)
    LinuxBackend().speak("read me", "en", 180)
    assert captured["cmd"][0] == "espeak-ng"
    assert "--stdin" in captured["cmd"]
    assert captured["text"] == b"read me" and captured["closed"]


def test_linux_speak_returns_none_when_no_engine(monkeypatch):
    monkeypatch.setattr(linux_backend.shutil, "which", lambda name: None)
    assert LinuxBackend().speak("x", None, 175) is None
