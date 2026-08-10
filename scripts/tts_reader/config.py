"""Config + data-directory paths for the TTS plugin.

Canonical data dir is ``~/.agent-tts`` (shared across hosts). Override with
``AGENT_TTS_DATA_DIR``. If the canonical dir is missing but the legacy Claude
path ``~/.claude/claude-code-tts`` still exists, that legacy dir is used so
existing config and daemon state stay coherent.

This deliberately does NOT use ``$CLAUDE_PLUGIN_DATA``: Claude Code only
injects that env var into hook subprocesses, not into the inline ``!`` bash
that runs the ``/tts`` slash command (``cli.py``). Keying off it would split
state across two different directories - config changes made via ``/tts on``
would never be visible to the Stop hook - which is exactly the bug that
motivated pinning this to one path both entry points can agree on.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "enabled": False,       # opt-in: nothing speaks until `/tts on`
    "mode": "summary",      # "summary" (lead paragraph) or "full"
    "prose_voice": None,    # None -> system default voice
    "header_voice": None,   # None -> fall back to prose voice (dual-voice off)
    "wpm": 175,             # words per minute
    "backend": "auto",      # auto | macos | windows | linux | cloud
    "cloud": {              # used only when backend == "cloud"
        "provider": "elevenlabs",  # elevenlabs | openai | azure
        "voice": None,             # provider voice id
        "api_key": None,           # optional; env var preferred (see engine/cloud.py)
        "region": None,            # azure only
    },
}

DATA_DIR_ENV = "AGENT_TTS_DATA_DIR"
CANONICAL_DIRNAME = ".agent-tts"
LEGACY_RELATIVE = (".claude", "claude-code-tts")


def data_dir() -> Path:
    """Resolve the shared plugin data directory (hook and CLI must agree)."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        d = Path(override).expanduser()
        d.mkdir(parents=True, exist_ok=True)
        return d

    home = Path.home()
    canonical = home / CANONICAL_DIRNAME
    legacy = home.joinpath(*LEGACY_RELATIVE)
    # Prefer the new shared dir; keep using legacy if it's the only one present
    # so existing config.json / daemon.port stay where they already are.
    if canonical.exists() or not legacy.exists():
        d = canonical
    else:
        d = legacy
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return data_dir() / "config.json"


def port_path() -> Path:
    """File the daemon writes ``"<port>\\n<token>"`` to for its TCP control
    channel. Replaces the old Unix-domain socket path so the daemon works on
    Windows (which lacks reliable ``AF_UNIX`` support)."""
    return data_dir() / "daemon.port"


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
    cfg["cloud"] = dict(DEFAULT_CONFIG["cloud"])  # own copy of the nested dict
    p = config_path()
    if p.exists():
        try:
            stored = json.loads(p.read_text())
        except (ValueError, OSError):
            stored = {}  # corrupt config -> fall back to defaults
        if isinstance(stored, dict):
            # deep-merge the nested cloud dict so a partial stored value (e.g.
            # only a saved api_key) doesn't drop the other cloud defaults
            stored_cloud = stored.pop("cloud", None)
            cfg.update(stored)
            if isinstance(stored_cloud, dict):
                cfg["cloud"].update(stored_cloud)
    return cfg


def save_config(cfg: dict) -> None:
    config_path().write_text(json.dumps(cfg, indent=2) + "\n")


def set_values(**changes) -> dict:
    cfg = load_config()
    cfg.update({k: v for k, v in changes.items() if v is not None})
    save_config(cfg)
    return cfg


def set_cloud_values(**changes) -> dict:
    """Update keys inside the nested ``cloud`` config block."""
    cfg = load_config()
    cfg["cloud"].update({k: v for k, v in changes.items() if v is not None})
    save_config(cfg)
    return cfg
