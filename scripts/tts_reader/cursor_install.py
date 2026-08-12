"""Merge-safe helper that installs Cursor TTS hooks, slash command, and skill.

Used by ``hosts/cursor/install.sh``. Pure functions so tests can exercise the
merge without touching a real ``~/.cursor/`` tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

PLACEHOLDER = "REPLACE_WITH_CHECKOUT"


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


def render_template(text: str, checkout: Path) -> str:
    """Substitute ``REPLACE_WITH_CHECKOUT`` with the absolute checkout path."""
    root = str(checkout.resolve())
    return text.replace(PLACEHOLDER, root)


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


def write_templated_file(src: Path, dest: Path, checkout: Path) -> Path:
    """Render a host template into ``dest`` (creates parents)."""
    if not src.is_file():
        raise SystemExit(f"missing Cursor install template: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        render_template(src.read_text(encoding="utf-8"), checkout),
        encoding="utf-8",
    )
    return dest


def install_command_and_skill(
    checkout: Path,
    *,
    commands_dir: Optional[Path] = None,
    skills_dir: Optional[Path] = None,
) -> Tuple[Path, Path]:
    """Write ``~/.cursor/commands/tts.md`` and ``~/.cursor/skills/tts/SKILL.md``."""
    root = checkout.resolve()
    hosts = root / "hosts" / "cursor"
    cmd_dest = (commands_dir or (Path.home() / ".cursor" / "commands")) / "tts.md"
    skill_dest = (
        skills_dir or (Path.home() / ".cursor" / "skills" / "tts")
    ) / "SKILL.md"
    write_templated_file(hosts / "commands" / "tts.md", cmd_dest, root)
    write_templated_file(hosts / "skills" / "tts" / "SKILL.md", skill_dest, root)
    return cmd_dest, skill_dest


def install(
    checkout: Optional[Path] = None,
    hooks_file: Optional[Path] = None,
    *,
    commands_dir: Optional[Path] = None,
    skills_dir: Optional[Path] = None,
    skip_commands: bool = False,
) -> Tuple[Path, str, Optional[Path], Optional[Path]]:
    """Install stop hook (+ optional slash command/skill); return paths."""
    root = (checkout or default_checkout_root()).resolve()
    if not (root / "scripts" / "tts_reader" / "hook_cursor.py").is_file():
        raise SystemExit(f"not an agent-tts checkout: {root}")
    dest = hooks_file or Path.home() / ".cursor" / "hooks.json"
    existing = load_hooks_file(dest)
    doc = merge_cursor_hooks(existing, root)
    write_hooks_file(dest, doc)
    cmd_path: Optional[Path] = None
    skill_path: Optional[Path] = None
    if not skip_commands:
        cmd_path, skill_path = install_command_and_skill(
            root, commands_dir=commands_dir, skills_dir=skills_dir
        )
    return dest, stop_command(root), cmd_path, skill_path


def main(argv: Optional[list] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Install Cursor TTS stop hook + /tts command"
    )
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
    p.add_argument(
        "--commands-dir",
        type=Path,
        default=None,
        help="Target commands dir (default: ~/.cursor/commands)",
    )
    p.add_argument(
        "--skills-dir",
        type=Path,
        default=None,
        help="Target skill folder (default: ~/.cursor/skills/tts)",
    )
    p.add_argument(
        "--skip-commands",
        action="store_true",
        help="Only write hooks.json (no ~/.cursor/commands or skills)",
    )
    args = p.parse_args(argv)
    dest, cmd, cmd_path, skill_path = install(
        args.checkout,
        args.hooks_file,
        commands_dir=args.commands_dir,
        skills_dir=args.skills_dir,
        skip_commands=args.skip_commands,
    )
    print(f"Wrote Cursor stop hook to {dest}")
    print(f"command: {cmd}")
    if cmd_path is not None:
        print(f"Wrote Cursor /tts command to {cmd_path}")
    if skill_path is not None:
        print(f"Wrote Cursor tts skill to {skill_path}")
    print("Enable TTS:  scripts/run scripts/tts_reader/cli.py on")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
