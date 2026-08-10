"""Stop-hook entrypoint.

Runs after every turn. It is deliberately dumb and fast: it does NOT read the
response text itself, just signals the daemon to speak this turn on the auto
channel, then exits 0 so it never blocks Claude. All failures are swallowed -
a broken TTS setup must not break turns.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_reader import client, config  # noqa: E402
from tts_reader.daemon import AUTO  # noqa: E402


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except ValueError:
        config.debug_log("hook_bad_stdin", raw=raw[:500])
        return

    if config.consume_command_suppression():
        config.debug_log("hook_skip_command_echo", session_id=payload.get("session_id"))
        return  # this turn was just a /tts command's own echoed confirmation

    cfg = config.load_config()
    if not cfg.get("enabled"):
        config.debug_log("hook_skip_disabled", session_id=payload.get("session_id"))
        return  # opt-in: silent until `/tts on`

    req = {
        "type": "speak",
        "channel": AUTO,
        "session_id": payload.get("session_id", "?"),
        "transcript_path": payload.get("transcript_path", ""),
        "cwd": payload.get("cwd", os.getcwd()),
        "mode": cfg.get("mode", "summary"),
    }
    resp = client.send(req)
    config.debug_log(
        "hook_sent",
        session_id=req["session_id"],
        transcript_path=req["transcript_path"],
        transcript_exists=os.path.exists(req["transcript_path"]),
        mode=req["mode"],
        resp=resp,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never break a turn
        config.debug_log("hook_exception", error=repr(exc))
    sys.exit(0)
