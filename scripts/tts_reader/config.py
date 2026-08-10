"""Config + data-directory paths for the TTS plugin.

Everything lives under a single fixed data dir: ``~/.claude/claude-code-tts``.
That dir holds the JSON config, the daemon's control socket, its pid file, and
its log.

This deliberately does NOT use ``$CLAUDE_PLUGIN_DATA``: Claude Code only
injects that env var into hook subprocesses, not into the inline ``!`` bash
that runs the ``/tts`` slash command (``cli.py``). Keying off it would split
state across two different directories - config changes made via ``/tts on``
would never be visible to the Stop hook - which is exactly the bug that
motivated pinning this to one path both entry points can agree on.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_CONFIG = {
    "enabled": False,       # opt-in: nothing speaks until `/tts on`
    "mode": "summary",      # "summary" (lead paragraph) or "full"
    "prose_voice": None,    # None -> macOS system default voice
    "header_voice": None,   # None -> fall back to prose voice (dual-voice off)
    "wpm": 175,             # words per minute
}


def data_dir() -> Path:
    d = Path.home() / ".claude" / "claude-code-tts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return data_dir() / "config.json"


def socket_path() -> Path:
    return data_dir() / "daemon.sock"


def pid_path() -> Path:
    return data_dir() / "daemon.pid"


def log_path() -> Path:
    return data_dir() / "daemon.log"


def debug_log_path() -> Path:
    return data_dir() / "debug.log"


def suppress_marker_path() -> Path:
    return data_dir() / "suppress_auto"


def mark_command_run() -> None:
    """Flag that a ``/tts`` command just ran, so its own echoed confirmation
    text isn't also auto-spoken by the Stop hook of that same relay turn.

    cli.py's output (e.g. "Replaying last response.", "TTS enabled.") is
    meta-output about the plugin, not a real Claude response, and for
    ``/tts replay`` in particular the actual audio is already produced by the
    explicit replay job - the Stop hook auto-speaking the confirmation text on
    top of that is what caused the same reply to be heard multiple times.
    """
    import time as _time

    suppress_marker_path().write_text(str(_time.time()))


def consume_command_suppression(max_age: float = 60.0) -> bool:
    """Single-use check: True if a ``/tts`` command ran just before this call.

    Consumes (deletes) the marker so it only ever suppresses the one Stop
    event immediately following the command, not a later unrelated turn.
    """
    import time as _time

    p = suppress_marker_path()
    if not p.exists():
        return False
    try:
        age = _time.time() - float(p.read_text())
    except (ValueError, OSError):
        age = 0.0
    try:
        p.unlink()
    except OSError:
        pass
    return age <= max_age


def debug_log(event: str, **fields) -> None:
    """Append a one-line trace event. Best-effort; never raises.

    Separate from ``daemon.log`` (subprocess stdout/stderr) so hook.py - which
    runs as its own short-lived process, not inside the daemon - can also
    record what it saw without needing the daemon's log handle.
    """
    try:
        import json
        import time as _time

        line = json.dumps({"ts": _time.time(), "event": event, **fields})
        with open(debug_log_path(), "a") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    p = config_path()
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text()))
        except (ValueError, OSError):
            pass  # corrupt config -> fall back to defaults
    return cfg


def save_config(cfg: dict) -> None:
    config_path().write_text(json.dumps(cfg, indent=2) + "\n")


def set_values(**changes) -> dict:
    cfg = load_config()
    cfg.update({k: v for k, v in changes.items() if v is not None})
    save_config(cfg)
    return cfg
