"""The backend interface every TTS engine implements.

A backend turns text into audible speech. ``speak`` must be *non-blocking*: it
starts playback and returns the running ``subprocess.Popen`` handle so the
daemon can (a) ``proc.wait()`` for it to finish and (b) ``proc.terminate()`` to
cut it off mid-sentence. Every backend - the OS engines and the cloud provider
alike - honours that contract, which is why the daemon's session-arbitration
and interrupt logic (daemon.py) needs no per-backend special-casing.
"""

from __future__ import annotations

import subprocess
from typing import List, Optional, Tuple


class Backend:
    """Common interface for all speech backends."""

    #: Human-facing name, used in ``/tts status`` and error messages.
    name = "base"

    def speak(
        self, text: str, voice: Optional[str], wpm: int
    ) -> Optional[subprocess.Popen]:
        """Start speaking ``text`` and return the running process.

        Returns ``None`` if playback could not be started (e.g. a missing
        engine or, for cloud, a missing API key); callers treat that as "spoke
        nothing" and move on - a broken backend must never break a turn.
        """
        raise NotImplementedError

    def list_voices(self) -> List[Tuple[str, str, str]]:
        """Return ``(name, locale, sample)`` for every selectable voice."""
        raise NotImplementedError
