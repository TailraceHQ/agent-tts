"""Thin wrapper around the macOS ``say`` command.

The daemon speaks one utterance at a time by spawning a ``say`` subprocess and
tracking its handle so playback can be interrupted (``proc.terminate()``).
"""

from __future__ import annotations

import re
import subprocess
from typing import List, Optional, Tuple

_VOICE_LINE_RE = re.compile(r"^(.*?)\s{2,}([a-z]{2}[-_][A-Z]{2})\s+#\s*(.*)$")


def speak(text: str, voice: Optional[str] = None, wpm: int = 175) -> subprocess.Popen:
    """Start speaking ``text`` and return the running subprocess (non-blocking)."""
    cmd = ["say", "-r", str(int(wpm))]
    if voice:
        cmd += ["-v", voice]
    cmd.append(text)
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def parse_voice_lines(text: str) -> List[Tuple[str, str, str]]:
    """Parse the output of ``say -v ?`` into ``(name, locale, sample)`` tuples."""
    voices: List[Tuple[str, str, str]] = []
    for line in text.splitlines():
        m = _VOICE_LINE_RE.match(line)
        if m:
            voices.append((m.group(1).strip(), m.group(2), m.group(3).strip()))
    return voices


def list_voices() -> List[Tuple[str, str, str]]:
    """Return ``(name, locale, sample)`` for every installed voice."""
    try:
        out = subprocess.run(
            ["say", "-v", "?"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return parse_voice_lines(out)
