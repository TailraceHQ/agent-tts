"""Read the *final* assistant text of a turn from a Claude Code transcript.

Why the player reads the transcript instead of the hook: the Stop hook fires
fractionally before the turn's closing message is flushed to disk. Reading at
hook time would return the previous turn's answer, or - for a tool-calling
turn - the "let me check that" preamble that precedes the tool calls. So we
poll the transcript here, from the player, until the current turn's final text
block has actually landed.

The transcript format is internal to Claude Code and can change between
versions, so every access is defensive.
"""

from __future__ import annotations

import glob
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


def project_dir_for_cwd(cwd: str) -> Path:
    """Claude Code stores a project's transcripts under a slugified cwd."""
    slug = cwd.replace(os.sep, "-")
    return Path.home() / ".claude" / "projects" / slug


def latest_transcript_for_cwd(cwd: str) -> Optional[str]:
    """Newest ``*.jsonl`` transcript for the given working directory."""
    d = project_dir_for_cwd(cwd)
    files = glob.glob(str(d / "*.jsonl"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _entry_timestamp(obj: dict) -> float:
    ts = obj.get("timestamp") or obj.get("ts")
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _assistant_text(obj: dict) -> str:
    """Extract concatenated text blocks from an assistant entry, else ""."""
    msg = obj.get("message", obj)
    role = obj.get("type") or msg.get("role")
    if role not in ("assistant",):
        return ""
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts).strip()


def _scan_final(path: str) -> Tuple[Optional[str], float]:
    """Return (last non-empty assistant text, its timestamp) from the file."""
    text, ts = None, 0.0
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                t = _assistant_text(obj)
                if t:
                    text, ts = t, _entry_timestamp(obj)
    except OSError:
        return None, 0.0
    return text, ts


def read_final_text(
    path: str, timeout: float = 3.0, poll: float = 0.15
) -> Optional[str]:
    """Poll ``path`` until the turn's final assistant text is present.

    By the time the Stop hook fires, the turn's own text is already flushed
    to disk - ``_scan_final`` reads to the true end of the (append-only) file,
    so the first scan already returns this turn's answer, not a stale one.
    The poll loop exists only for the rare case where the transcript write is
    still lagging: keep checking until *some* assistant text shows up, capped
    by ``timeout``.

    (An earlier version gated on ``entry_timestamp >= request_ts``, a
    timestamp captured by the caller *after* the entry was already written -
    an ordering that can never hold, so every call burned the full timeout
    before falling back to the very text it found on the first scan. That
    added a needless ~3s of dead air before every response.)
    """
    if not path or not Path(path).exists():
        return None
    deadline = time.time() + timeout
    while True:
        text, _ts = _scan_final(path)
        if text:
            return text
        if time.time() >= deadline:
            return None
        time.sleep(poll)
