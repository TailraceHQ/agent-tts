"""Config + data-directory paths for the TTS plugin.

Everything lives under a single data dir: ``$CLAUDE_PLUGIN_DATA`` when Claude
Code provides it, otherwise ``~/.claude/claude-code-tts``. That dir holds the
JSON config, the daemon's control socket, its pid file, and its log.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "enabled": False,       # opt-in: nothing speaks until `/tts on`
    "mode": "summary",      # "summary" (lead paragraph) or "full"
    "prose_voice": None,    # None -> macOS system default voice
    "header_voice": None,   # None -> fall back to prose voice (dual-voice off)
    "wpm": 175,             # words per minute
}


def data_dir() -> Path:
    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    d = Path(base) if base else Path.home() / ".claude" / "claude-code-tts"
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
