"""Pluggable TTS backends + the factory that picks one.

The rest of the codebase talks to this package through three names -
``get_backend``, ``speak`` and ``list_voices`` - so swapping the macOS-only
``say`` engine for per-OS engines plus a cloud provider stayed a local change.

``get_backend(cfg)`` resolves the active backend from config:
  * ``"auto"`` (default) -> the current operating system's built-in engine
  * ``"macos" | "windows" | "linux"`` -> force a specific OS engine
  * ``"cloud"`` -> a hosted provider (see cloud.py)
"""

from __future__ import annotations

import platform
import subprocess
from typing import List, Optional, Tuple

from .base import Backend
from .macos import parse_voice_lines  # re-exported for tests / callers

__all__ = ["Backend", "get_backend", "speak", "list_voices", "parse_voice_lines"]


def _os_backend_name() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Windows":
        return "windows"
    return "linux"


def get_backend(cfg: Optional[dict] = None) -> Backend:
    choice = (cfg or {}).get("backend", "auto")
    if choice == "auto":
        choice = _os_backend_name()

    if choice == "cloud":
        from .cloud import CloudBackend
        return CloudBackend()
    if choice == "windows":
        from .windows import WindowsBackend
        return WindowsBackend()
    if choice == "linux":
        from .linux import LinuxBackend
        return LinuxBackend()
    # default / "macos"
    from .macos import MacOSBackend
    return MacOSBackend()


def speak(
    text: str, voice: Optional[str], wpm: int, cfg: Optional[dict] = None
) -> Optional[subprocess.Popen]:
    return get_backend(cfg).speak(text, voice, wpm)


def list_voices(cfg: Optional[dict] = None) -> List[Tuple[str, str, str]]:
    return get_backend(cfg).list_voices()
