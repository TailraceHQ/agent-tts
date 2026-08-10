"""macOS backend: the built-in ``say`` command.

This is the original engine, unchanged in behaviour - ``say`` speaks one
utterance per spawned subprocess and is interrupted with ``proc.terminate()``.
"""

from __future__ import annotations

import re
import subprocess
from typing import List, Optional, Tuple

from .base import Backend

_VOICE_LINE_RE = re.compile(r"^(.*?)\s{2,}([a-z]{2}[-_][A-Z]{2})\s+#\s*(.*)$")


def parse_voice_lines(text: str) -> List[Tuple[str, str, str]]:
    """Parse the output of ``say -v ?`` into ``(name, locale, sample)`` tuples."""
    voices: List[Tuple[str, str, str]] = []
    for line in text.splitlines():
        m = _VOICE_LINE_RE.match(line)
        if m:
            voices.append((m.group(1).strip(), m.group(2), m.group(3).strip()))
    return voices


class MacOSBackend(Backend):
    name = "macos"

    def speak(
        self, text: str, voice: Optional[str], wpm: int
    ) -> Optional[subprocess.Popen]:
        cmd = ["say", "-r", str(int(wpm))]
        if voice:
            cmd += ["-v", voice]
        cmd.append(text)
        try:
            return subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except OSError:
            return None

    def list_voices(self) -> List[Tuple[str, str, str]]:
        try:
            out = subprocess.run(
                ["say", "-v", "?"], capture_output=True, text=True, check=True
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            return []
        return parse_voice_lines(out)
