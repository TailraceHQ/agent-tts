"""`/tts` subcommand dispatcher.

Invoked by the slash command as:
    python3 .../cli.py <subcommand> [args...]

Config changes (on/off/summary/full/voice/wpm) just edit the JSON config and
print a one-line confirmation. replay/stop talk to the daemon. preview renders
the utterance queue locally without speaking - the debugging workhorse.
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
    "usage: /tts <on|off|summary|full|replay|stop|preview|status|voices|"
    "voice prose|header <name>|wpm <n>>"
)


def _current_transcript() -> str | None:
    return transcript.latest_transcript_for_cwd(os.getcwd())


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


def cmd_full(_):
    config.set_values(mode="full")
    return "Mode: full (whole response)."


def cmd_stop(_):
    client.send({"type": "stop", "session_id": None}, autostart=False)
    return "Playback stopped."


def cmd_replay(_):
    path = _current_transcript()
    if not path:
        return "Nothing to replay: no transcript found for this session."
    cfg = config.load_config()
    client.send({
        "type": "speak",
        "channel": REPLAY,
        "session_id": os.getcwd(),  # replay is keyed to this window
        "transcript_path": path,
        "cwd": os.getcwd(),
        "mode": cfg.get("mode", "summary"),
        "request_ts": 0.0,  # replay the last message that's already on disk
    })
    return "Replaying last response."


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


def cmd_voices(_):
    voices = engine.list_voices()
    if not voices:
        return "No voices found (is this macOS with `say` installed?)."
    lines = [f"{name}  [{loc}]" for name, loc, _ in voices]
    return "Installed voices:\n" + "\n".join(lines)


def cmd_status(_):
    cfg = config.load_config()
    dv = "on" if cfg.get("header_voice") else "off"
    return (
        f"enabled={cfg['enabled']}  mode={cfg['mode']}  wpm={cfg['wpm']}\n"
        f"prose_voice={cfg['prose_voice'] or 'system default'}  "
        f"header_voice={cfg['header_voice'] or '(same as prose)'}  dual_voice={dv}"
    )


def cmd_preview(_):
    path = _current_transcript()
    if not path:
        return "Nothing to preview: no transcript found for this session."
    text = transcript.read_final_text(path, request_ts=0.0, timeout=1.0)
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
    "full": cmd_full,
    "stop": cmd_stop,
    "replay": cmd_replay,
    "voice": cmd_voice,
    "wpm": cmd_wpm,
    "voices": cmd_voices,
    "status": cmd_status,
    "preview": cmd_preview,
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
    print(handler(rest))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
