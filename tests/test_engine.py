"""Tests for parsing `say -v ?` output (voice listing)."""

from tts_reader import engine

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
