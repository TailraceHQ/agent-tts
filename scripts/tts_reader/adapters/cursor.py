"""Stub: map Cursor Agent stop-hook stdin into a SpeakRequest.

Phase 0 finding: live Cursor transcripts were not captured in this environment.
Field names below come from public Cursor hook docs; the transcript *format*
reader is not implemented yet (Claude JSONL reader remains the only one).

Expected stdin (documented): conversation_id, transcript_path, workspace_roots,
status (completed|aborted|error), hook_event_name.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional

from tts_reader.adapters.common import SpeakRequest


def from_stop_payload(
    payload: Mapping[str, Any],
    *,
    mode: str = "summary",
    channel: str = "auto",
    text: Optional[str] = None,
) -> SpeakRequest:
    roots = payload.get("workspace_roots") or []
    cwd = roots[0] if isinstance(roots, list) and roots else os.getcwd()
    return SpeakRequest(
        session_id=str(payload.get("conversation_id") or "?"),
        transcript_path=str(payload.get("transcript_path") or ""),
        text=text,
        cwd=str(cwd),
        channel=channel,
        mode=mode,
    )
