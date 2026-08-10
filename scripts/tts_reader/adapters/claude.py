"""Map Claude Code Stop-hook stdin into a SpeakRequest."""

from __future__ import annotations

import os
from typing import Any, Mapping

from tts_reader.adapters.common import SpeakRequest


def from_stop_payload(
    payload: Mapping[str, Any],
    *,
    mode: str = "summary",
    channel: str = "auto",
) -> SpeakRequest:
    """Claude Stop stdin: session_id, transcript_path, cwd, hook_event_name."""
    return SpeakRequest(
        session_id=str(payload.get("session_id") or "?"),
        transcript_path=str(payload.get("transcript_path") or ""),
        cwd=str(payload.get("cwd") or os.getcwd()),
        channel=channel,
        mode=mode,
    )
