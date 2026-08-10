"""Linux backend: ``espeak-ng`` (preferred) or ``spd-say`` (fallback).

``espeak-ng`` plays audio directly from the spawned process, so
``proc.terminate()`` stops speech instantly - exactly the interrupt behaviour
the daemon relies on. ``spd-say`` instead hands the utterance to the
speech-dispatcher daemon and returns, so killing it does *not* reliably cut
playback; it is only used when ``espeak-ng`` is unavailable. Text is passed on
stdin to avoid argument-length and quoting issues.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import List, Optional, Tuple

from .base import Backend

# spd-say's rate is -100..100 (0 = default). Map wpm onto it, treating 175 wpm
# as the neutral midpoint. espeak-ng takes wpm directly, so needs no mapping.
_WPM_BASELINE = 175


def wpm_to_spd_rate(wpm: int) -> int:
    rate = round((int(wpm) - _WPM_BASELINE) / _WPM_BASELINE * 100)
    return max(-100, min(100, rate))


class LinuxBackend(Backend):
    name = "linux"

    def _command(self, voice: Optional[str], wpm: int) -> Optional[List[str]]:
        if shutil.which("espeak-ng"):
            cmd = ["espeak-ng", "-s", str(int(wpm)), "--stdin"]
            if voice:
                cmd[1:1] = ["-v", voice]
            return cmd
        if shutil.which("spd-say"):
            cmd = ["spd-say", "-w", "-e", "-r", str(wpm_to_spd_rate(wpm))]
            if voice:
                cmd += ["-y", voice]
            return cmd
        return None

    def speak(
        self, text: str, voice: Optional[str], wpm: int
    ) -> Optional[subprocess.Popen]:
        cmd = self._command(voice, wpm)
        if cmd is None:
            return None
        # spd-say reads its text as an argument, espeak-ng from stdin
        use_stdin = cmd[0] == "espeak-ng"
        if not use_stdin:
            cmd = cmd + [text]
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE if use_stdin else subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return None
        if use_stdin:
            try:
                proc.stdin.write(text.encode("utf-8"))
                proc.stdin.close()
            except OSError:
                pass
        return proc

    def list_voices(self) -> List[Tuple[str, str, str]]:
        if not shutil.which("espeak-ng"):
            return []
        try:
            out = subprocess.run(
                ["espeak-ng", "--voices"], capture_output=True, text=True, check=True
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            return []
        voices: List[Tuple[str, str, str]] = []
        for line in out.splitlines()[1:]:  # skip the header row
            cols = line.split()
            if len(cols) >= 4:
                locale, name = cols[1], cols[3]
                voices.append((name, locale, ""))
        return voices
