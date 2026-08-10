"""Tests for the cloud TTS backend.

The network is fully mocked: we stub ``_post`` (the single HTTP entry point) to
capture what each provider would send, and stub the audio player so nothing
actually plays. Covers request shape per provider, the missing-key no-op, and
that a successful synth is handed to the player.
"""

import pytest

from tts_reader import config
from tts_reader.engine import cloud
from tts_reader.engine.cloud import CloudBackend


@pytest.fixture(autouse=True)
def clear_provider_env(monkeypatch):
    for var in ("ELEVENLABS_API_KEY", "OPENAI_API_KEY", "AZURE_SPEECH_KEY"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def captured_post(monkeypatch):
    calls = []

    def fake_post(url, data, headers):
        calls.append({"url": url, "data": data, "headers": headers})
        return b"AUDIO"

    monkeypatch.setattr(cloud, "_post", fake_post)
    return calls


@pytest.fixture
def captured_play(monkeypatch):
    played = {}

    def fake_play(path):
        played["path"] = path
        return "PLAYER_PROC"

    monkeypatch.setattr(cloud.player, "play", fake_play)
    return played


def test_missing_key_is_a_noop(monkeypatch, captured_play):
    # no api_key in config and no env var -> nothing synthesized or played
    posts = []
    monkeypatch.setattr(cloud, "_post", lambda *a, **k: posts.append(a) or b"x")
    config.set_cloud_values(provider="elevenlabs", api_key=None)
    assert CloudBackend().speak("hello", None, 175) is None
    assert posts == [] and "path" not in captured_play


def test_elevenlabs_request(captured_post, captured_play):
    config.set_cloud_values(provider="elevenlabs", api_key="K", voice="VOICE1")
    proc = CloudBackend().speak("hello world", None, 175)
    assert proc == "PLAYER_PROC"
    call = captured_post[-1]
    assert call["url"].endswith("/text-to-speech/VOICE1")
    assert call["headers"]["xi-api-key"] == "K"
    assert b"hello world" in call["data"]
    assert captured_play["path"].endswith(".mp3")


def test_openai_request_maps_speed(captured_post, captured_play):
    config.set_cloud_values(provider="openai", api_key="K", voice="nova")
    CloudBackend().speak("hi", None, 350)  # 2x baseline -> speed 2.0
    call = captured_post[-1]
    assert call["url"].endswith("/audio/speech")
    assert call["headers"]["Authorization"] == "Bearer K"
    assert b'"speed": 2.0' in call["data"]
    assert b'"voice": "nova"' in call["data"]
    assert captured_play["path"].endswith(".wav")


def test_azure_requires_region(monkeypatch, captured_play):
    posts = []
    monkeypatch.setattr(cloud, "_post", lambda *a, **k: posts.append(a) or b"x")
    config.set_cloud_values(provider="azure", api_key="K", region=None)
    assert CloudBackend().speak("hi", None, 175) is None
    assert posts == []


def test_azure_request_builds_ssml(captured_post, captured_play):
    config.set_cloud_values(provider="azure", api_key="K",
                            voice="en-US-JennyNeural", region="eastus")
    CloudBackend().speak("hi <there>", None, 175)
    call = captured_post[-1]
    assert "eastus.tts.speech.microsoft.com" in call["url"]
    assert call["headers"]["Ocp-Apim-Subscription-Key"] == "K"
    body = call["data"].decode("utf-8")
    assert "en-US-JennyNeural" in body
    assert "&lt;there&gt;" in body  # xml-escaped


def test_env_var_key_is_used(monkeypatch, captured_post, captured_play):
    monkeypatch.setenv("OPENAI_API_KEY", "envkey")
    config.set_cloud_values(provider="openai", api_key=None, voice="alloy")
    CloudBackend().speak("hi", None, 175)
    assert captured_post[-1]["headers"]["Authorization"] == "Bearer envkey"


def test_explicit_voice_overrides_cloud_default(captured_post, captured_play):
    # a per-utterance voice (e.g. header voice) takes precedence over cfg voice
    config.set_cloud_values(provider="elevenlabs", api_key="K", voice="CFG")
    CloudBackend().speak("hi", "PERUTT", 175)
    assert captured_post[-1]["url"].endswith("/text-to-speech/PERUTT")
