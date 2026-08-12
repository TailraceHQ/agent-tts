"""Map Cursor Agent stop-hook stdin into a SpeakRequest.

Documented stdin fields: conversation_id, transcript_path, workspace_roots,
status (completed|aborted|error), hook_event_name.

Transcript lines are role-nested JSONL
(``{"role":"assistant","message":{"content":[...]}}``), plus roleless status
lines such as ``{"type":"turn_ended"}``. On-disk discovery uses
``~/.cursor/projects/<slug>/agent-transcripts/`` when replaying without a
hook-supplied path.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional

from tts_reader.adapters.common import SpeakRequest


def should_speak(payload: Mapping[str, Any]) -> bool:
    """Only speak completed agent loops; skip aborted/error stops."""
    return payload.get("status") == "completed"


def from_stop_payload(
    payload: Mapping[str, Any],
    *,
    mode: str = "summary",
    channel: str = "auto",
    text: Optional[str] = None,
) -> SpeakRequest:
    roots = payload.get("workspace_roots") or []
    cwd = roots[0] if isinstance(roots, list) and roots else os.getcwd()
    path = payload.get("transcript_path")
    return SpeakRequest(
        session_id=str(payload.get("conversation_id") or "?"),
        transcript_path=str(path or ""),
        text=text,
        cwd=str(cwd),
        channel=channel,
        mode=mode,
    )
