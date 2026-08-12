"""Read the *final* assistant text of a turn from a host transcript.

Why the player reads the transcript instead of the hook: the Stop hook fires
fractionally before the turn's closing message is flushed to disk. Reading at
hook time would return the previous turn's answer, or - for a tool-calling
turn - the "let me check that" preamble that precedes the tool calls. So we
poll the transcript here, from the player, until the current turn's final text
block has actually landed.

Supported JSONL shapes (defensive; host formats can change):

* Claude Code: ``type=assistant`` + ``message.content`` text blocks
* Cursor: role-nested ``role=assistant`` + ``message.content``
* Antigravity: step logs with ``source=MODEL``, ``type=PLANNER_RESPONSE``,
  string ``content`` (see MemPalace / Antigravity docs)

Discovery for ``/tts replay`` / ``preview`` is host-pluggable: last speak
pointer, then Claude / Cursor / Antigravity locators for the cwd.
"""

from __future__ import annotations

import glob
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


def project_dir_for_cwd(cwd: str) -> Path:
    """Claude Code stores a project's transcripts under a slugified cwd."""
    slug = cwd.replace(os.sep, "-")
    return Path.home() / ".claude" / "projects" / slug


def cursor_project_slug(cwd: str) -> str:
    """Cursor project dir name under ``~/.cursor/projects/``."""
    p = cwd.replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        # Windows drive: C:/Users/... -> C/Users/...
        p = p[0] + p[2:]
    return p.lstrip("/").replace("/", "-")


def cursor_project_dir_for_cwd(cwd: str) -> Path:
    return Path.home() / ".cursor" / "projects" / cursor_project_slug(cwd)


def antigravity_brain_roots() -> List[Path]:
    """Candidate Antigravity app-data brain directories (IDE + CLI variants)."""
    home = Path.home()
    return [
        home / ".gemini" / "antigravity-ide" / "brain",
        home / ".gemini" / "antigravity" / "brain",
        home / ".gemini" / "antigravity-cli" / "brain",
    ]


def latest_claude_transcript(cwd: str) -> Optional[str]:
    """Newest Claude ``*.jsonl`` transcript for the given working directory."""
    d = project_dir_for_cwd(cwd)
    files = glob.glob(str(d / "*.jsonl"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def latest_cursor_transcript(cwd: str) -> Optional[str]:
    """Newest Cursor agent-transcript under ``~/.cursor/projects/<slug>/``."""
    root = cursor_project_dir_for_cwd(cwd) / "agent-transcripts"
    if not root.is_dir():
        return None
    files = [
        p for p in root.rglob("*.jsonl")
        if "subagents" not in p.parts
    ]
    if not files:
        return None
    return str(max(files, key=lambda p: p.stat().st_mtime))


def latest_antigravity_transcript(cwd: str) -> Optional[str]:
    """Newest Antigravity ``transcript.jsonl`` whose brain looks related to cwd.

    Prefer transcripts that mention ``cwd`` in a sibling workspace marker or
    whose parent path is under a known brain root. When multiple conversations
    exist, pick the newest ``transcript.jsonl`` (not ``transcript_full``).
    """
    candidates: List[Path] = []
    for brain in antigravity_brain_roots():
        if not brain.is_dir():
            continue
        for path in brain.glob("*/.system_generated/logs/transcript.jsonl"):
            candidates.append(path)
        # Some installs nest logs differently or use project-local jetski paths;
        # also accept any transcript.jsonl one level under brain/*/logs/
        for path in brain.glob("*/logs/transcript.jsonl"):
            candidates.append(path)
    # Project-local paths seen in MemPalace examples:
    #   <cwd>/.gemini/jetski/transcript.jsonl
    local = Path(cwd) / ".gemini" / "jetski" / "transcript.jsonl"
    if local.is_file():
        candidates.append(local)
    if not candidates:
        return None
    return str(max(candidates, key=lambda p: p.stat().st_mtime))


# Back-compat alias used by older tests / callers.
def latest_transcript_for_cwd(cwd: str) -> Optional[str]:
    """Newest transcript for cwd across known hosts (see ``discover_transcript``)."""
    return discover_transcript(cwd)


def discover_transcript(cwd: str) -> Optional[str]:
    """Resolve a transcript for replay/preview.

    Order:
      1. Last speak job's ``transcript_path`` (when still on disk)
      2. Claude Code project transcripts for ``cwd``
      3. Cursor agent-transcripts for ``cwd``
      4. Antigravity brain / project-local transcripts
    """
    from tts_reader import config  # local import: avoid import cycle at module load

    remembered = config.load_last_speak()
    if remembered:
        path = remembered.get("transcript_path") or ""
        if path and Path(path).is_file():
            return path

    for locator in (
        latest_claude_transcript,
        latest_cursor_transcript,
        latest_antigravity_transcript,
    ):
        path = locator(cwd)
        if path:
            return path
    return None


def _entry_timestamp(obj: dict) -> float:
    ts = obj.get("timestamp") or obj.get("ts") or obj.get("created_at")
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _claude_or_cursor_text(obj: dict) -> str:
    """Extract text from Claude type=assistant or Cursor role-nested lines."""
    msg = obj.get("message", obj)
    role = obj.get("type") or obj.get("role") or (
        msg.get("role") if isinstance(msg, dict) else None
    )
    if role not in ("assistant",):
        return ""
    if not isinstance(msg, dict):
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


def _antigravity_text(obj: dict) -> str:
    """Extract speakable text from an Antigravity step-log line.

    Final answers are ``PLANNER_RESPONSE`` rows with non-empty ``content``.
    Rows that only schedule ``tool_calls`` (no content) are skipped so we do
    not speak tool-result dumps from ``SEARCH_WEB`` / similar step types.
    """
    source = str(obj.get("source") or "").upper()
    step_type = str(obj.get("type") or "").upper()
    if source != "MODEL" or step_type != "PLANNER_RESPONSE":
        return ""
    content = obj.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    return ""


def _assistant_text(obj: dict) -> str:
    """Extract concatenated assistant/final text from one JSONL object."""
    if not isinstance(obj, dict):
        return ""
    # Antigravity step shape uses source/type that would not match Claude roles.
    if obj.get("source") is not None or (
        isinstance(obj.get("type"), str)
        and obj.get("type") not in ("assistant", "user", "system")
        and "message" not in obj
    ):
        ag = _antigravity_text(obj)
        if ag:
            return ag
        # Fall through: some hybrid lines may still be Claude-shaped.
    return _claude_or_cursor_text(obj)


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
