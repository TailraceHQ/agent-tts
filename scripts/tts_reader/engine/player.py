"""Play a synthesized audio file, cross-platform.

Used only by the cloud backend, which fetches audio bytes from a provider and
needs to play them. Returns the player ``subprocess.Popen`` so it obeys the
same ``wait()`` / ``terminate()`` contract as the OS speech backends.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from typing import List, Optional


def _macos_cmd(path: str) -> List[str]:
    return ["afplay", path]


def _windows_cmd(path: str) -> List[str]:
    # (Play synchronously so the process stays alive for the whole clip; a
    # WAV uses SoundPlayer, anything else falls through to MediaPlayer.)
    script = (
        f"$p = '{path}';"
        "if ([IO.Path]::GetExtension($p) -ieq '.wav') {"
        " (New-Object System.Media.SoundPlayer $p).PlaySync() } else {"
        " Add-Type -AssemblyName presentationCore;"
        " $m = New-Object System.Windows.Media.MediaPlayer;"
        " $m.Open([uri]$p); $m.Play();"
        " while ($m.NaturalDuration.HasTimeSpan -eq $false) { Start-Sleep -m 50 };"
        " Start-Sleep -s $m.NaturalDuration.TimeSpan.TotalSeconds }"
    )
    return ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]


def _linux_cmd(path: str) -> Optional[List[str]]:
    if shutil.which("ffplay"):
        return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]
    if shutil.which("mpg123") and path.lower().endswith(".mp3"):
        return ["mpg123", "-q", path]
    if shutil.which("aplay") and path.lower().endswith(".wav"):
        return ["aplay", "-q", path]
    if shutil.which("paplay"):
        return ["paplay", path]
    return None


def play(path: str) -> Optional[subprocess.Popen]:
    """Start playing the audio file at ``path``; return the player process."""
    system = platform.system()
    if system == "Darwin":
        cmd: Optional[List[str]] = _macos_cmd(path)
    elif system == "Windows":
        cmd = _windows_cmd(path)
    else:
        cmd = _linux_cmd(path)
    if cmd is None:
        return None
    try:
        return subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except OSError:
        return None
