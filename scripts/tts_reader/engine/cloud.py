"""Cloud backend: synthesize each utterance through a hosted TTS provider.

Lets a user plug in *their own* voice by supplying an API key (from a named
environment variable, or stored key) and a provider voice id
(``tts cloud setup`` or ``/tts backend cloud`` + ``/tts cloud ...``). ``speak`` is
synth-then-play: fetch audio bytes over HTTPS (stdlib ``urllib`` only, to keep
the plugin dependency-free), write them to a temp file, and hand the file to
``player.play`` - whose returned process obeys the same wait/terminate contract
as the OS backends.

A missing or invalid key never raises: ``speak`` logs via ``config.debug_log``
and returns ``None`` so the turn completes silently rather than breaking.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import List, Optional, Tuple

from .. import config
from .base import Backend
from . import player

_TIMEOUT = 30.0
_AUDIO_TTL = 120.0  # seconds; prune synthesized temp clips older than this

# Per-provider fallback voice when the user hasn't chosen one.
_DEFAULT_VOICE = {
    "elevenlabs": "21m00Tcm4TlvDq8ikWAM",  # "Rachel"
    "openai": "alloy",
    "azure": "en-US-JennyNeural",
}
DEFAULT_API_KEY_ENV = {
    "elevenlabs": "ELEVENLABS_API_KEY",
    "openai": "OPENAI_API_KEY",
    "azure": "AZURE_SPEECH_KEY",
}
_ENV_KEY = DEFAULT_API_KEY_ENV
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def valid_env_name(name: str) -> bool:
    return bool(name) and _ENV_NAME_RE.fullmatch(name) is not None


def api_key_env_name(provider: str, cloud: Optional[dict] = None) -> Optional[str]:
    """Env var to read for this provider. Honors a user-named ``api_key_env``."""
    custom = (cloud or {}).get("api_key_env")
    if isinstance(custom, str) and custom.strip():
        return custom.strip()
    return DEFAULT_API_KEY_ENV.get(provider)


def key_source(cloud: dict) -> str:
    """Where the key would come from (never the secret). For ``tts status``."""
    if cloud.get("api_key"):
        return "stored"
    provider = cloud.get("provider", "elevenlabs")
    name = api_key_env_name(provider, cloud)
    if not name:
        return "none"
    if os.environ.get(name):
        return f"env:{name}"
    return f"missing:{name}"


def _api_key(provider: str, cloud: dict) -> Optional[str]:
    stored = cloud.get("api_key")
    if stored:
        return stored
    name = api_key_env_name(provider, cloud)
    if not name:
        return None
    return os.environ.get(name) or None


# -- HTTPS / CA bundle --------------------------------------------------------
# python.org macOS builds ship OpenSSL without a CA bundle until the user runs
# "Install Certificates.command". urllib then fails with
# CERTIFICATE_VERIFY_FAILED, which we swallow so a TTS miss never breaks a
# turn. Prefer an existing default store; otherwise load certifi, SSL_CERT_FILE,
# a well-known system bundle, or (on macOS) the SystemRootCertificates keychain.

_SSL_CTX = None  # type: Optional[ssl.SSLContext]
_MACOS_ROOTS_TTL = 7 * 24 * 3600
_MACOS_KEYCHAIN = (
    "/System/Library/Keychains/SystemRootCertificates.keychain"
)
_CAFILE_CANDIDATES = (
    "/etc/ssl/cert.pem",
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/usr/local/etc/openssl@3/cert.pem",
)


def reset_ssl_context() -> None:
    """Drop the cached SSL context (tests)."""
    global _SSL_CTX
    _SSL_CTX = None


def ssl_verify_hint() -> str:
    if sys.platform == "darwin":
        return (
            "This Python has no usable CA bundle, so cloud HTTPS fails. "
            "python.org installers: run "
            "/Applications/Python 3.x/Install Certificates.command "
            "(or: python3 -m pip install certifi). "
            "Then kill the TTS daemon so it restarts: "
            "kill \"$(cat ~/.agent-tts/daemon.pid)\""
        )
    return (
        "This Python has no usable CA bundle, so cloud HTTPS fails. "
        "Set SSL_CERT_FILE to a CA bundle (for example "
        "/etc/ssl/certs/ca-certificates.crt) and restart the TTS daemon."
    )


def _cert_count(ctx: ssl.SSLContext) -> int:
    try:
        stats = ctx.cert_store_stats()
    except Exception:
        return 0
    return int(stats.get("x509_ca") or 0) + int(stats.get("x509") or 0)


def _macos_system_roots_pem() -> Optional[str]:
    cache = config.data_dir() / "certs" / "macos-system-roots.pem"
    try:
        if cache.is_file() and time.time() - cache.stat().st_mtime < _MACOS_ROOTS_TTL:
            return str(cache)
    except OSError:
        pass
    try:
        proc = subprocess.run(
            ["security", "find-certificate", "-a", "-p", _MACOS_KEYCHAIN],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or b"-----BEGIN CERTIFICATE-----" not in proc.stdout:
        return None
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(proc.stdout)
        return str(cache)
    except OSError:
        return None


def _cafile_candidates() -> List[str]:
    out: List[str] = []
    for env_name in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        value = os.environ.get(env_name)
        if value:
            out.append(value)
    try:
        import certifi  # optional; python.org "Install Certificates" installs it

        where = certifi.where()
        if where:
            out.append(where)
    except Exception:
        pass
    try:
        paths = ssl.get_default_verify_paths()
        for path in (paths.cafile, paths.openssl_cafile):
            if path:
                out.append(path)
    except Exception:
        pass
    out.extend(_CAFILE_CANDIDATES)
    return out


def ssl_context() -> ssl.SSLContext:
    """Default SSL context, with a CA bundle loaded if the store is empty."""
    global _SSL_CTX
    if _SSL_CTX is not None:
        return _SSL_CTX
    ctx = ssl.create_default_context()
    if _cert_count(ctx) > 0:
        _SSL_CTX = ctx
        return ctx
    seen = set()
    for path in _cafile_candidates():
        if not path or path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        try:
            ctx.load_verify_locations(cafile=path)
        except (OSError, ssl.SSLError):
            continue
        if _cert_count(ctx) > 0:
            config.debug_log("cloud_ssl_cafile", path=path)
            _SSL_CTX = ctx
            return ctx
    if sys.platform == "darwin":
        mac = _macos_system_roots_pem()
        if mac and mac not in seen:
            try:
                ctx.load_verify_locations(cafile=mac)
            except (OSError, ssl.SSLError):
                pass
            else:
                if _cert_count(ctx) > 0:
                    config.debug_log("cloud_ssl_cafile", path=mac)
                    _SSL_CTX = ctx
                    return ctx
    config.debug_log("cloud_ssl_no_ca")
    _SSL_CTX = ctx
    return ctx


def ssl_status_warning() -> Optional[str]:
    """One-line status warning when this interpreter cannot verify HTTPS."""
    if _cert_count(ssl_context()) > 0:
        return None
    return "warning: no CA certificates; cloud HTTPS will fail silently"


def _is_cert_verify_error(exc: BaseException) -> bool:
    text = repr(exc)
    reason = getattr(exc, "reason", None)
    if reason is not None:
        text += repr(reason)
    return "CERTIFICATE_VERIFY_FAILED" in text or "SSLCertVerificationError" in text


def _urlopen(req: urllib.request.Request):
    return urllib.request.urlopen(req, timeout=_TIMEOUT, context=ssl_context())


def _post(url: str, data: bytes, headers: dict) -> Optional[bytes]:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with _urlopen(req) as resp:
            return resp.read()
    except (urllib.error.URLError, OSError) as exc:
        if _is_cert_verify_error(exc):
            config.debug_log(
                "cloud_ssl_error",
                error=repr(exc),
                url=url,
                hint=ssl_verify_hint(),
            )
        else:
            config.debug_log("cloud_http_error", error=repr(exc), url=url)
        return None


# -- providers: each returns (audio_bytes, file_extension) or None ------------


def _synth_elevenlabs(text, voice, wpm, key, cloud) -> Optional[Tuple[bytes, str]]:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    body = json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode()
    audio = _post(url, body, {
        "xi-api-key": key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    })
    return (audio, ".mp3") if audio else None


def _synth_openai(text, voice, wpm, key, cloud) -> Optional[Tuple[bytes, str]]:
    speed = max(0.25, min(4.0, int(wpm) / 175.0))
    body = json.dumps({
        "model": "gpt-4o-mini-tts",
        "voice": voice,
        "input": text,
        "response_format": "wav",
        "speed": round(speed, 2),
    }).encode()
    audio = _post("https://api.openai.com/v1/audio/speech", body, {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    return (audio, ".wav") if audio else None


def _synth_azure(text, voice, wpm, key, cloud) -> Optional[Tuple[bytes, str]]:
    region = cloud.get("region")
    if not region:
        config.debug_log("cloud_azure_no_region")
        return None
    rate_pct = round((int(wpm) / 175.0 - 1.0) * 100)
    ssml = (
        "<speak version='1.0' xml:lang='en-US'>"
        f"<voice name='{voice}'>"
        f"<prosody rate='{rate_pct:+d}%'>{_xml_escape(text)}</prosody>"
        "</voice></speak>"
    )
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    audio = _post(url, ssml.encode("utf-8"), {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
        "User-Agent": "agent-tts",
    })
    return (audio, ".wav") if audio else None


_SYNTH = {
    "elevenlabs": _synth_elevenlabs,
    "openai": _synth_openai,
    "azure": _synth_azure,
}


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _audio_dir():
    d = config.data_dir() / "audio"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _prune_old_audio() -> None:
    now = time.time()
    try:
        for f in _audio_dir().iterdir():
            try:
                if now - f.stat().st_mtime > _AUDIO_TTL:
                    f.unlink()
            except OSError:
                pass
    except OSError:
        pass


class CloudBackend(Backend):
    name = "cloud"

    def speak(
        self, text: str, voice: Optional[str], wpm: int
    ) -> Optional[subprocess.Popen]:
        cloud = config.load_config().get("cloud", {})
        provider = cloud.get("provider", "elevenlabs")
        synth = _SYNTH.get(provider)
        if synth is None:
            config.debug_log("cloud_unknown_provider", provider=provider)
            return None
        key = _api_key(provider, cloud)
        if not key:
            config.debug_log("cloud_no_key", provider=provider)
            return None
        # explicit per-utterance voice (prose/header) wins over the cloud default
        voice_id = voice or cloud.get("voice") or _DEFAULT_VOICE.get(provider)

        result = synth(text, voice_id, wpm, key, cloud)
        if not result:
            return None
        audio, ext = result

        _prune_old_audio()
        try:
            fd, path = tempfile.mkstemp(suffix=ext, dir=str(_audio_dir()))
            with os.fdopen(fd, "wb") as fh:
                fh.write(audio)
        except OSError as exc:
            config.debug_log("cloud_write_error", error=repr(exc))
            return None
        return player.play(path)

    def list_voices(self) -> List[Tuple[str, str, str]]:
        cloud = config.load_config().get("cloud", {})
        provider = cloud.get("provider", "elevenlabs")
        key = _api_key(provider, cloud)
        if provider == "elevenlabs" and key:
            return self._elevenlabs_voices(key)
        # Without a live listing, surface the provider's default so the user has
        # at least one known-good id to start from.
        default = _DEFAULT_VOICE.get(provider)
        return [(default, provider, "")] if default else []

    def _elevenlabs_voices(self, key: str) -> List[Tuple[str, str, str]]:
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key}
        )
        try:
            with _urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            if _is_cert_verify_error(exc):
                config.debug_log(
                    "cloud_ssl_error",
                    error=repr(exc),
                    hint=ssl_verify_hint(),
                )
            else:
                config.debug_log("cloud_voices_error", error=repr(exc))
            return []
        out: List[Tuple[str, str, str]] = []
        for v in data.get("voices", []):
            vid = v.get("voice_id", "")
            name = v.get("name", "")
            out.append((f"{name} ({vid})", v.get("category", ""), ""))
        return out
