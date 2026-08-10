"""Windows backend: SAPI via PowerShell's ``System.Speech.Synthesis``.

Text is fed to PowerShell on **stdin** (``[Console]::In.ReadToEnd()``) rather
than as a command-line argument - Windows caps command lines around 32 KB and
quoting arbitrary prose is a minefield. We write the text, close stdin, and
return the process; ``proc.wait()`` blocks until it finishes speaking and
``proc.terminate()`` kills PowerShell to cut playback off.
"""

from __future__ import annotations

import subprocess
from typing import List, Optional, Tuple

from .base import Backend

# SAPI's rate scale is an integer -10..10, with 0 as the engine default (which
# sounds like roughly ~175 wpm). Map words-per-minute onto that scale so the
# `/tts wpm` control keeps working; ~25 wpm per rate step is a good fit.
_WPM_BASELINE = 175
_WPM_PER_STEP = 25


def wpm_to_sapi_rate(wpm: int) -> int:
    rate = round((int(wpm) - _WPM_BASELINE) / _WPM_PER_STEP)
    return max(-10, min(10, rate))


def _ps_quote(s: str) -> str:
    """Quote a string for a PowerShell single-quoted literal."""
    return "'" + s.replace("'", "''") + "'"


class WindowsBackend(Backend):
    name = "windows"

    def _script(self, voice: Optional[str], wpm: int) -> str:
        parts = [
            "Add-Type -AssemblyName System.Speech;",
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;",
            f"$s.Rate = {wpm_to_sapi_rate(wpm)};",
        ]
        if voice:
            parts.append(f"$s.SelectVoice({_ps_quote(voice)});")
        parts.append("$s.Speak([Console]::In.ReadToEnd())")
        return " ".join(parts)

    def speak(
        self, text: str, voice: Optional[str], wpm: int
    ) -> Optional[subprocess.Popen]:
        cmd = [
            "powershell", "-NoProfile", "-NonInteractive",
            "-Command", self._script(voice, wpm),
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return None
        try:
            proc.stdin.write(text.encode("utf-8"))
            proc.stdin.close()
        except OSError:
            pass
        return proc

    def list_voices(self) -> List[Tuple[str, str, str]]:
        script = (
            "Add-Type -AssemblyName System.Speech;"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            "$s.GetInstalledVoices() | ForEach-Object {"
            " $i = $_.VoiceInfo;"
            " Write-Output ($i.Name + '\\t' + $i.Culture.Name) }"
        )
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, check=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            return []
        voices: List[Tuple[str, str, str]] = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            name, _, loc = line.partition("\t")
            voices.append((name.strip(), loc.strip(), ""))
        return voices
