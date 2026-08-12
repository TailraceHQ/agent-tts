"""Merge-safe helper that installs the Cursor stop hook into hooks.json.

Used by ``hosts/cursor/install.sh``. Pure functions so tests can exercise the
merge without touching a real ``~/.cursor/hooks.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def default_checkout_root() -> Path:
    """Repo root: scripts/tts_reader/cursor_install.py → ../../.."""
    return Path(__file__).resolve().parents[2]


def stop_command(checkout: Path) -> str:
    root = checkout.resolve()
    run = root / "scripts" / "run"
    hook = root / "scripts" / "tts_reader" / "hook_cursor.py"
    return f"{run} {hook}"


def merge_cursor_hooks(
    existing: Optional[Dict[str, Any]],
    checkout: Path,
    *,
    timeout: int = 10,
) -> Dict[str, Any]:
    """Return a hooks.json document with our stop command merged in.

    Preserves unrelated hooks. Replaces any prior stop entry that points at
    ``hook_cursor.py`` / ``tts_reader`` so re-running install is idempotent.
    """
    doc: Dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
    doc.setdefault("version", 1)
    hooks = doc.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        doc["hooks"] = hooks
    stop = hooks.get("stop")
    if not isinstance(stop, list):
        stop = []
    cmd = stop_command(checkout)
    kept = []
    for entry in stop:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        c = str(entry.get("command") or "")
        if "hook_cursor.py" in c or "tts_reader/hook_cursor" in c:
            continue
        kept.append(entry)
    kept.append({"command": cmd, "timeout": timeout})
    hooks["stop"] = kept
    return doc


def load_hooks_file(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def write_hooks_file(path: Path, doc: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def install(
    checkout: Optional[Path] = None,
    hooks_file: Optional[Path] = None,
) -> Tuple[Path, str]:
    """Merge our stop hook into ``hooks_file``; return (path, command)."""
    root = (checkout or default_checkout_root()).resolve()
    if not (root / "scripts" / "tts_reader" / "hook_cursor.py").is_file():
        raise SystemExit(f"not a claude-code-tts checkout: {root}")
    dest = hooks_file or Path.home() / ".cursor" / "hooks.json"
    existing = load_hooks_file(dest)
    doc = merge_cursor_hooks(existing, root)
    write_hooks_file(dest, doc)
    return dest, stop_command(root)


def main(argv: Optional[list] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Install Cursor TTS stop hook")
    p.add_argument(
        "--checkout",
        type=Path,
        default=None,
        help="Repo checkout (default: detect from this file)",
    )
    p.add_argument(
        "--hooks-file",
        type=Path,
        default=None,
        help="Target hooks.json (default: ~/.cursor/hooks.json)",
    )
    args = p.parse_args(argv)
    dest, cmd = install(args.checkout, args.hooks_file)
    print(f"Wrote Cursor stop hook to {dest}")
    print(f"command: {cmd}")
    print("Enable TTS:  scripts/run scripts/tts_reader/cli.py on")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
