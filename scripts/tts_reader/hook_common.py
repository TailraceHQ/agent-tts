"""Shared Stop-hook runner used by host-specific entry points.

Fail-open: every path exits 0. Host adapters decide whether a payload should
speak; this module handles stdin, config gating, daemon notify, and optional
empty-object stdout (Cursor / Antigravity require ``{}`` and must never emit
follow-up / continue decisions).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable, Mapping, Optional

from tts_reader import client, config
from tts_reader.adapters.common import SpeakRequest
from tts_reader.daemon import AUTO

MapFn = Callable[..., SpeakRequest]
GateFn = Callable[[Mapping[str, Any]], bool]


def run_stop_hook(
    *,
    map_payload: MapFn,
    should_speak: Optional[GateFn] = None,
    emit_empty_stdout: bool = False,
    host: str = "unknown",
) -> None:
    """Read Stop stdin, optionally speak, always exit without raising."""
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        config.debug_log(f"{host}_hook_bad_stdin", raw=raw[:500])
        _finish(emit_empty_stdout)
        return

    if not isinstance(payload, dict):
        config.debug_log(f"{host}_hook_bad_payload_type")
        _finish(emit_empty_stdout)
        return

    if config.consume_command_suppression():
        config.debug_log(
            f"{host}_hook_skip_command_echo",
            session_id=payload.get("session_id")
            or payload.get("conversation_id")
            or payload.get("conversationId"),
        )
        _finish(emit_empty_stdout)
        return

    cfg = config.load_config()
    if not cfg.get("enabled"):
        config.debug_log(
            f"{host}_hook_skip_disabled",
            session_id=payload.get("session_id")
            or payload.get("conversation_id")
            or payload.get("conversationId"),
        )
        _finish(emit_empty_stdout)
        return

    if should_speak is not None and not should_speak(payload):
        config.debug_log(f"{host}_hook_skip_gated", payload_keys=sorted(payload.keys()))
        _finish(emit_empty_stdout)
        return

    speak = map_payload(payload, mode=cfg.get("mode", "summary"), channel=AUTO)
    req = speak.to_daemon_req()
    # Remember path for `/tts replay` on hosts that do not use Claude's layout.
    config.remember_last_speak(
        req.get("transcript_path") or "",
        cwd=req.get("cwd") or "",
        host=host,
    )
    resp = client.send(req)
    config.debug_log(
        f"{host}_hook_sent",
        session_id=req["session_id"],
        transcript_path=req["transcript_path"],
        transcript_exists=os.path.exists(req["transcript_path"]),
        mode=req["mode"],
        resp=resp,
    )
    _finish(emit_empty_stdout)


def _finish(emit_empty_stdout: bool) -> None:
    if emit_empty_stdout:
        # Cursor followup_message / Antigravity decision:continue must never
        # appear here. Always a bare empty object.
        sys.stdout.write("{}\n")
        sys.stdout.flush()
