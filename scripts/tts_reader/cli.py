"""`/tts` subcommand dispatcher.

Invoked by the slash command as:
    python3 .../cli.py <subcommand> [args...]

Config changes (on/off/summary/closing/brief/full/voice/wpm) just edit the JSON
config and print a one-line confirmation. replay/stop/skip/pause/resume talk
to the daemon. preview renders the utterance queue locally without speaking.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_reader import client, config, engine, transcript  # noqa: E402
from tts_reader.daemon import AUTO, REPLAY  # noqa: E402
from tts_reader.sanitize import sanitize  # noqa: E402

USAGE = (
    "usage: tts <on|off|summary|closing|brief|full|replay [mode]|stop|skip|"
    "pause|resume|preview|status|migrate|voices|voice prose|header <name>|"
    "wpm <n>|backend <auto|macos|windows|linux|cloud>|setup|"
    "cloud [setup]|cloud <provider|voice|key|env|region> <value>>"
)

MODES = ("summary", "closing", "brief", "full")
BACKENDS = ("auto", "macos", "windows", "linux", "cloud")
CLOUD_PROVIDERS = ("elevenlabs", "openai", "azure")


def _current_transcript() -> str | None:
    """Locate a transcript for replay/preview (Claude, Cursor, or Antigravity)."""
    return transcript.discover_transcript(os.getcwd())


def cmd_on(_):
    config.set_values(enabled=True)
    return "TTS enabled."


def cmd_off(_):
    config.set_values(enabled=False)
    client.send({"type": "stop", "session_id": None}, autostart=False)
    return "TTS disabled."


def cmd_summary(_):
    config.set_values(mode="summary")
    return "Mode: summary (lead paragraph only)."


def cmd_closing(_):
    config.set_values(mode="closing")
    return "Mode: closing (last paragraph only)."


def cmd_brief(_):
    config.set_values(mode="brief")
    return "Mode: brief (first sentence of the lead paragraph)."


def cmd_full(_):
    config.set_values(mode="full")
    return "Mode: full (whole cleaned response)."


def cmd_stop(_):
    client.send({"type": "stop", "session_id": None}, autostart=False)
    return "Playback stopped."


def _daemon_control(kind: str, ok_key: str, idle: str, done: str) -> str:
    resp = client.send({"type": kind, "session_id": None}, autostart=False)
    if not resp or not resp.get(ok_key):
        return idle
    return done


def cmd_skip(_):
    return _daemon_control(
        "skip",
        "skipped",
        "Nothing to skip: TTS is not speaking.",
        "Skipped current utterance.",
    )


def cmd_pause(_):
    return _daemon_control(
        "pause",
        "paused",
        "Nothing to pause: TTS is not speaking.",
        "Paused.",
    )


def cmd_resume(_):
    return _daemon_control(
        "resume",
        "resumed",
        "Nothing to resume: TTS is not paused.",
        "Resumed.",
    )


def cmd_replay(args):
    if args and args[0] not in MODES:
        return f"usage: tts replay [{' | '.join(MODES)}]"
    path = _current_transcript()
    if not path:
        return "Nothing to replay: no transcript found for this session."
    cfg = config.load_config()
    mode = args[0] if args else cfg.get("mode", "summary")
    client.send({
        "type": "speak",
        "channel": REPLAY,
        "session_id": os.getcwd(),  # replay is keyed to this window
        "transcript_path": path,
        "cwd": os.getcwd(),
        "mode": mode,
    })
    return f"Replaying last response ({mode})."


def cmd_voice(args):
    if len(args) < 2 or args[0] not in ("prose", "header"):
        return "usage: /tts voice <prose|header> <voice-name>"
    key = "prose_voice" if args[0] == "prose" else "header_voice"
    name = " ".join(args[1:])
    config.set_values(**{key: name})
    return f"{args[0].capitalize()} voice set to {name}."


def cmd_wpm(args):
    if not args or not args[0].isdigit():
        return "usage: /tts wpm <number>"
    config.set_values(wpm=int(args[0]))
    return f"Speaking rate set to {args[0]} words per minute."


def cmd_backend(args):
    if not args or args[0] not in BACKENDS:
        return f"usage: /tts backend <{'|'.join(BACKENDS)}>"
    config.set_values(backend=args[0])
    return f"Backend set to {args[0]}."


def cmd_setup(_):
    from tts_reader.cloud_setup import run_wizard

    return run_wizard()


def cmd_cloud(args):
    usage = (
        "usage: /tts cloud [setup]\n"
        "       /tts cloud <provider|voice|key|env|region> <value>\n"
        f"  provider: {' | '.join(CLOUD_PROVIDERS)}"
    )
    if not args or args[0] in ("setup", "wizard"):
        return cmd_setup([])
    if len(args) < 2 or args[0] not in ("provider", "voice", "key", "env", "region"):
        return usage
    field, value = args[0], " ".join(args[1:])
    if field == "provider":
        if value not in CLOUD_PROVIDERS:
            return f"unknown provider {value!r}. choose: {', '.join(CLOUD_PROVIDERS)}"
        config.set_cloud_values(provider=value)
        return f"Cloud provider set to {value}."
    if field == "env":
        from tts_reader.engine.cloud import valid_env_name

        if not valid_env_name(value):
            return (
                f"invalid env var name {value!r}. "
                "use letters, digits, and underscores."
            )
        config.set_cloud_values(api_key_env=value)
        return f"Cloud API key env var set to {value}."
    key = {"voice": "voice", "key": "api_key", "region": "region"}[field]
    config.set_cloud_values(**{key: value})
    shown = "(hidden)" if field == "key" else value
    return f"Cloud {field} set to {shown}."


def cmd_voices(_):
    cfg = config.load_config()
    voices = engine.list_voices(cfg)
    if not voices:
        return (
            "No voices found for the active backend "
            f"({cfg.get('backend', 'auto')}). Is its TTS engine installed?"
        )
    lines = [f"{name}  [{loc}]" for name, loc, _ in voices]
    return "Installed voices:\n" + "\n".join(lines)


def cmd_status(_):
    cfg = config.load_config()
    dv = "on" if cfg.get("header_voice") else "off"
    lines = [
        f"enabled={cfg['enabled']}  mode={cfg['mode']}  wpm={cfg['wpm']}",
        f"prose_voice={cfg['prose_voice'] or 'system default'}  "
        f"header_voice={cfg['header_voice'] or '(same as prose)'}  dual_voice={dv}",
        f"backend={cfg.get('backend', 'auto')}",
        f"data_dir={config.data_dir()}",
    ]
    if cfg.get("backend") == "cloud":
        from tts_reader.engine.cloud import key_source, ssl_status_warning

        cl = cfg.get("cloud", {})
        lines.append(
            f"cloud: provider={cl.get('provider')}  "
            f"voice={cl.get('voice') or '(provider default)'}  "
            f"api_key={key_source(cl)}"
        )
        warn = ssl_status_warning()
        if warn:
            lines.append(warn)
    return "\n".join(lines)


def cmd_migrate(_):
    """Copy legacy ~/.claude/claude-code-tts → ~/.agent-tts if needed."""
    result = config.migrate_legacy_data_dir()
    path = result.get("path") or str(config.canonical_data_dir())
    if result.get("migrated"):
        copied = ", ".join(result.get("copied") or []) or "(nothing new)"
        legacy = result.get("legacy", "")
        return (
            f"Migrated to {path}\n"
            f"copied: {copied}\n"
            f"legacy left at {legacy} (safe to delete after confirming TTS works)."
        )
    reason = result.get("reason")
    if reason == "no_legacy":
        return f"Nothing to migrate; using {path}."
    if reason == "canonical_exists":
        legacy = result.get("legacy")
        extra = f"\nlegacy still present at {legacy}" if legacy else ""
        return f"Already using {path}.{extra}"
    if reason == "error":
        return f"Migration failed: {result.get('error')}"
    return f"Nothing to migrate ({reason}); using {path}."


def cmd_preview(_):
    path = _current_transcript()
    if not path:
        return "Nothing to preview: no transcript found for this session."
    text = transcript.read_final_text(path, timeout=1.0)
    if not text:
        return "Nothing to preview: no assistant message found."
    cfg = config.load_config()
    utterances = sanitize(text, cfg.get("mode", "summary"))
    if not utterances:
        return "(empty utterance queue)"
    prose_v = cfg.get("prose_voice") or "default"
    header_v = cfg.get("header_voice") or prose_v
    lines = [f"utterance queue (mode={cfg.get('mode')}):"]
    for u in utterances:
        v = header_v if u.voice == "header" else prose_v
        lines.append(f"  [{u.voice}:{v}] {u.text}")
    return "\n".join(lines)


COMMANDS = {
    "on": cmd_on,
    "off": cmd_off,
    "summary": cmd_summary,
    "closing": cmd_closing,
    "brief": cmd_brief,
    "full": cmd_full,
    "stop": cmd_stop,
    "skip": cmd_skip,
    "pause": cmd_pause,
    "resume": cmd_resume,
    "replay": cmd_replay,
    "voice": cmd_voice,
    "wpm": cmd_wpm,
    "voices": cmd_voices,
    "status": cmd_status,
    "preview": cmd_preview,
    "backend": cmd_backend,
    "cloud": cmd_cloud,
    "setup": cmd_setup,
    "migrate": cmd_migrate,
}


def main(argv) -> int:
    if not argv:
        print(USAGE)
        return 0
    sub, rest = argv[0].lower(), argv[1:]
    handler = COMMANDS.get(sub)
    if not handler:
        print(f"unknown subcommand {sub!r}\n{USAGE}")
        return 0
    config.mark_command_run()
    print(handler(rest))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
