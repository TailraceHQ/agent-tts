"""Stub: map Google Antigravity Stop-hook stdin into a SpeakRequest.

Phase 0 finding: live Antigravity transcripts were not captured here. Field
names below come from public Antigravity hook docs; a dedicated transcript
reader is deferred until sample transcripts exist.

Expected stdin (documented): conversationId, transcriptPath, workspacePaths,
fullyIdle, terminationReason.
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
    paths = payload.get("workspacePaths") or []
    cwd = paths[0] if isinstance(paths, list) and paths else os.getcwd()
    return SpeakRequest(
        session_id=str(payload.get("conversationId") or "?"),
        transcript_path=str(payload.get("transcriptPath") or ""),
        text=text,
        cwd=str(cwd),
        channel=channel,
        mode=mode,
    )
