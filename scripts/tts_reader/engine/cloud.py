"""Cloud backend: synthesize each utterance through a hosted TTS provider.

Lets a user plug in *their own* voice by supplying an API key and a provider
voice id (``/tts backend cloud`` + ``/tts cloud ...``). ``speak`` is
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
import subprocess
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
_ENV_KEY = {
    "elevenlabs": "ELEVENLABS_API_KEY",
    "openai": "OPENAI_API_KEY",
    "azure": "AZURE_SPEECH_KEY",
}


def _api_key(provider: str, cloud: dict) -> Optional[str]:
    return cloud.get("api_key") or os.environ.get(_ENV_KEY.get(provider, ""))


def _post(url: str, data: bytes, headers: dict) -> Optional[bytes]:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.read()
    except (urllib.error.URLError, OSError) as exc:
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
        "User-Agent": "claude-code-tts",
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
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            config.debug_log("cloud_voices_error", error=repr(exc))
            return []
        out: List[Tuple[str, str, str]] = []
        for v in data.get("voices", []):
            vid = v.get("voice_id", "")
            name = v.get("name", "")
            out.append((f"{name} ({vid})", v.get("category", ""), ""))
        return out
