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
    path: str, request_ts: float = 0.0, timeout: float = 3.0, poll: float = 0.15
) -> Optional[str]:
    """Poll ``path`` until the turn's final assistant text is present.

    If ``request_ts`` is given, wait for an assistant entry at least that fresh
    so we don't read the previous turn. Falls back to whatever final text is
    present once ``timeout`` elapses.
    """
    if not path or not Path(path).exists():
        return None
    deadline = time.time() + timeout
    last_seen = None
    while True:
        text, ts = _scan_final(path)
        last_seen = text if text else last_seen
        fresh_enough = ts >= request_ts if request_ts else True
        if text and fresh_enough:
            return text
        if time.time() >= deadline:
            return last_seen
        time.sleep(poll)
