"""Map Google Antigravity Stop-hook stdin into a SpeakRequest.

Documented stdin fields: conversationId, transcriptPath, workspacePaths,
fullyIdle, terminationReason, optional error.

Transcripts are step-log JSONL (``source`` / ``type`` / ``content``), not
Claude role messages. ``transcript.read_final_text`` takes the last
``MODEL`` + ``PLANNER_RESPONSE`` with non-empty ``content``.

Always return empty stdout ``{}`` from the hook entry — never
``{"decision":"continue"}``, which would restart the agent loop.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional

from tts_reader.adapters.common import SpeakRequest

# Clear failure / incomplete terminations — do not speak these.
_ERROR_REASONS = frozenset({
    "error",
    "max_steps_exceeded",
})


def should_speak(payload: Mapping[str, Any]) -> bool:
    """Speak only when the agent is fully idle and not in a clear failure."""
    if payload.get("fullyIdle") is not True:
        return False
    reason = str(payload.get("terminationReason") or "").lower()
    if reason in _ERROR_REASONS:
        return False
    err = payload.get("error")
    if isinstance(err, str) and err.strip():
        return False
    return True


def from_stop_payload(
    payload: Mapping[str, Any],
    *,
    mode: str = "summary",
    channel: str = "auto",
    text: Optional[str] = None,
) -> SpeakRequest:
    paths = payload.get("workspacePaths") or []
    cwd = paths[0] if isinstance(paths, list) and paths else os.getcwd()
    path = payload.get("transcriptPath")
    return SpeakRequest(
        session_id=str(payload.get("conversationId") or "?"),
        transcript_path=str(path or ""),
        text=text,
        cwd=str(cwd),
        channel=channel,
        mode=mode,
    )
