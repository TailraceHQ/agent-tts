"""Tests for the cloud TTS backend.

The network is fully mocked: we stub ``_post`` (the single HTTP entry point) to
capture what each provider would send, and stub the audio player so nothing
actually plays. Covers request shape per provider, the missing-key no-op, and
that a successful synth is handed to the player.
"""

import ssl
import urllib.error

import pytest

from tts_reader import config
from tts_reader.engine import cloud
from tts_reader.engine.cloud import CloudBackend


@pytest.fixture(autouse=True)
def isolated_cloud_env(monkeypatch):
    cloud.reset_ssl_context()
    for var in (
        "ELEVENLABS_API_KEY",
        "OPENAI_API_KEY",
        "AZURE_SPEECH_KEY",
        "OPEN_AI_ALLOY_VOICE_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    yield
    cloud.reset_ssl_context()


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


def test_custom_api_key_env_name(monkeypatch, captured_post, captured_play):
    monkeypatch.setenv("OPEN_AI_ALLOY_VOICE_KEY", "namedkey")
    monkeypatch.setenv("OPENAI_API_KEY", "defaultkey")
    config.set_cloud_values(
        provider="openai",
        api_key=None,
        voice="alloy",
        api_key_env="OPEN_AI_ALLOY_VOICE_KEY",
    )
    CloudBackend().speak("hi", None, 175)
    assert captured_post[-1]["headers"]["Authorization"] == "Bearer namedkey"


def test_custom_api_key_env_does_not_fall_back(monkeypatch, captured_play):
    monkeypatch.setenv("OPENAI_API_KEY", "defaultkey")
    posts = []
    monkeypatch.setattr(cloud, "_post", lambda *a, **k: posts.append(a) or b"x")
    config.set_cloud_values(
        provider="openai",
        api_key=None,
        voice="alloy",
        api_key_env="OPEN_AI_ALLOY_VOICE_KEY",
    )
    assert CloudBackend().speak("hi", None, 175) is None
    assert posts == []


def test_explicit_voice_overrides_cloud_default(captured_post, captured_play):
    # a per-utterance voice (e.g. header voice) takes precedence over cfg voice
    config.set_cloud_values(provider="elevenlabs", api_key="K", voice="CFG")
    CloudBackend().speak("hi", "PERUTT", 175)
    assert captured_post[-1]["url"].endswith("/text-to-speech/PERUTT")


class _EmptyStoreCtx:
    """SSLContext stand-in whose default store is empty until a cafile loads."""

    def __init__(self):
        self.loaded = None

    def cert_store_stats(self):
        if self.loaded:
            return {"x509_ca": 12, "x509": 0, "crl": 0}
        return {"x509_ca": 0, "x509": 0, "crl": 0}

    def load_verify_locations(self, cafile=None, **_k):
        self.loaded = cafile


def test_ssl_context_loads_ssl_cert_file_when_default_empty(monkeypatch, tmp_path):
    pem = tmp_path / "ca.pem"
    pem.write_text("-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n")
    monkeypatch.setenv("SSL_CERT_FILE", str(pem))
    ctx = _EmptyStoreCtx()
    monkeypatch.setattr(cloud.ssl, "create_default_context", lambda: ctx)
    monkeypatch.setattr(cloud, "_macos_system_roots_pem", lambda: None)
    got = cloud.ssl_context()
    assert got is ctx
    assert ctx.loaded == str(pem)
    assert cloud.ssl_status_warning() is None


def test_ssl_context_uses_macos_keychain_when_no_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(cloud.sys, "platform", "darwin")
    monkeypatch.setattr(cloud, "_cafile_candidates", lambda: [])
    roots = tmp_path / "roots.pem"
    roots.write_text("keychain")
    ctx = _EmptyStoreCtx()
    monkeypatch.setattr(cloud.ssl, "create_default_context", lambda: ctx)
    monkeypatch.setattr(cloud, "_macos_system_roots_pem", lambda: str(roots))
    got = cloud.ssl_context()
    assert got is ctx
    assert ctx.loaded == str(roots)


def test_post_logs_ssl_error_with_hint(monkeypatch):
    err = urllib.error.URLError(
        ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED")
    )
    monkeypatch.setattr(
        cloud.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(err),
    )
    logs = []
    monkeypatch.setattr(
        config, "debug_log", lambda event, **fields: logs.append((event, fields))
    )
    monkeypatch.setattr(cloud.sys, "platform", "darwin")
    assert cloud._post("https://api.openai.com/v1/audio/speech", b"{}", {}) is None
    assert logs and logs[0][0] == "cloud_ssl_error"
    assert "Install Certificates" in logs[0][1]["hint"]


def test_ssl_verify_hint_darwin():
    # imported sys.platform may be linux in CI; exercise the helper via patch
    import tts_reader.engine.cloud as c
    old = c.sys.platform
    try:
        c.sys.platform = "darwin"
        assert "Install Certificates.command" in c.ssl_verify_hint()
        c.sys.platform = "linux"
        assert "SSL_CERT_FILE" in c.ssl_verify_hint()
    finally:
        c.sys.platform = old
