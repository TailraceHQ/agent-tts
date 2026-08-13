"""Config + data-directory paths for the TTS plugin.

Canonical data dir is ``~/.agent-tts`` (shared across hosts). Override with
``AGENT_TTS_DATA_DIR``. If the canonical dir is missing but the legacy Claude
path ``~/.claude/claude-code-tts`` still exists, that legacy dir is **migrated**
(copied) into ``~/.agent-tts`` so existing config stays coherent. Live daemon
runtime files (pid/port/sock/log) are skipped so a new daemon starts under the
canonical path. The legacy directory is left in place with a marker file.

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
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CONFIG = {
    "enabled": False,       # opt-in: nothing speaks until `/tts on`
    "mode": "summary",      # summary | closing | brief | full
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
# Do not copy live daemon runtime — a new daemon binds under the canonical dir.
MIGRATE_SKIP = frozenset({
    "daemon.pid",
    "daemon.port",
    "daemon.sock",
    "daemon.log",
})
MIGRATED_MARKER = "MIGRATED_TO_AGENT_TTS"


def canonical_data_dir(home: Optional[Path] = None) -> Path:
    return (home or Path.home()) / CANONICAL_DIRNAME


def legacy_data_dir(home: Optional[Path] = None) -> Path:
    return (home or Path.home()).joinpath(*LEGACY_RELATIVE)


def migrate_legacy_data_dir(
    *,
    home: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Copy legacy ``~/.claude/claude-code-tts`` into ``~/.agent-tts`` if needed.

    Copies into a staging directory first and only publishes it via an atomic
    rename, so a mid-copy failure (disk full, unreadable file, ...) never
    leaves ``~/.agent-tts`` half-populated - the canonical dir either appears
    fully migrated or not at all, and a failed attempt can always be retried.
    This also makes concurrent callers (e.g. the Stop hook and the CLI running
    at once) safe: whichever finishes first publishes canonical, the other
    discards its staging copy.

    Returns a status dict with keys such as ``migrated``, ``reason``, ``path``,
    ``legacy``, and ``copied``. Safe to call repeatedly.
    """
    home_path = home or Path.home()
    canonical = canonical_data_dir(home_path)
    legacy = legacy_data_dir(home_path)

    if not legacy.is_dir():
        return {
            "migrated": False,
            "reason": "no_legacy",
            "path": str(canonical),
        }

    if canonical.exists() and not force:
        return {
            "migrated": False,
            "reason": "canonical_exists",
            "path": str(canonical),
            "legacy": str(legacy),
        }

    staging = canonical.parent / f".{CANONICAL_DIRNAME}.migrating-{os.getpid()}"
    copied: List[str] = []
    try:
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        for src in sorted(legacy.iterdir()):
            name = src.name
            if name in MIGRATE_SKIP or name == MIGRATED_MARKER:
                continue
            dest = staging / name
            if src.is_file():
                shutil.copy2(src, dest)
                copied.append(name)
            elif src.is_dir():
                shutil.copytree(src, dest)
                copied.append(name + "/")

        if canonical.exists():
            if not force:
                # Another process published canonical while we were copying.
                shutil.rmtree(staging, ignore_errors=True)
                return {
                    "migrated": False,
                    "reason": "canonical_exists",
                    "path": str(canonical),
                    "legacy": str(legacy),
                }
            shutil.rmtree(canonical)
        staging.rename(canonical)

        marker = legacy / MIGRATED_MARKER
        marker.write_text(
            f"Migrated to {canonical}\n"
            f"Safe to delete this legacy directory after confirming TTS works.\n",
            encoding="utf-8",
        )
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        return {
            "migrated": False,
            "reason": "error",
            "error": repr(exc),
            "path": str(canonical),
            "legacy": str(legacy),
            "copied": copied,
        }

    try:
        debug_log(
            "migrated_legacy_data_dir",
            legacy=str(legacy),
            canonical=str(canonical),
            copied=copied,
        )
    except Exception:
        pass

    return {
        "migrated": True,
        "reason": "copied",
        "path": str(canonical),
        "legacy": str(legacy),
        "copied": copied,
    }


def data_dir() -> Path:
    """Resolve the shared plugin data directory (hook and CLI must agree)."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        d = Path(override).expanduser()
        d.mkdir(parents=True, exist_ok=True)
        return d

    home = Path.home()
    canonical = canonical_data_dir(home)
    legacy = legacy_data_dir(home)
    # Prefer canonical. If only legacy exists, try to migrate. If migration
    # doesn't complete (error, or another process wins the race), fall back
    # to legacy so existing config/daemon state stay reachable - migration
    # is atomic (see migrate_legacy_data_dir), so partial copies never leave
    # canonical half-populated, and this same check will retry it next time.
    if not canonical.exists() and legacy.is_dir():
        migrate_legacy_data_dir(home=home)

    if canonical.exists() or not legacy.is_dir():
        canonical.mkdir(parents=True, exist_ok=True)
        return canonical
    return legacy


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


def last_speak_path() -> Path:
    """Pointer to the most recent auto-speak transcript (for CLI replay)."""
    return data_dir() / "last_speak.json"


def remember_last_speak(
    transcript_path: str,
    *,
    cwd: str = "",
    host: str = "",
) -> None:
    """Record the last speak job's transcript so replay works off Claude paths."""
    if not transcript_path:
        return
    try:
        import time as _time

        payload = {
            "transcript_path": transcript_path,
            "cwd": cwd or "",
            "host": host or "",
            "ts": _time.time(),
        }
        last_speak_path().write_text(json.dumps(payload) + "\n")
    except OSError:
        pass


def load_last_speak() -> Optional[dict]:
    """Return the last-speak pointer dict, or None if missing/corrupt."""
    p = last_speak_path()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


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
