"""Shared speak-request shape used by host adapters and the daemon client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SpeakRequest:
    """Host-neutral speak job.

    ``transcript_path`` is the Claude-style path to a JSONL transcript. Future
    hosts may omit it and pass ``text`` inline instead (or both). The daemon
    prefers ``text`` when present and non-empty, otherwise reads the transcript.
    """

    session_id: str
    transcript_path: str = ""
    text: Optional[str] = None
    cwd: str = ""
    channel: str = "auto"
    mode: str = "summary"

    def to_daemon_req(self) -> dict:
        req = {
            "type": "speak",
            "channel": self.channel,
            "session_id": self.session_id,
            "transcript_path": self.transcript_path,
            "cwd": self.cwd,
            "mode": self.mode,
        }
        if self.text is not None:
            req["text"] = self.text
        return req
