"""Stop-hook entrypoint.

Runs after every turn. It is deliberately dumb and fast: it does NOT read the
response text (the transcript isn't reliably flushed yet). It just signals the
daemon to speak this turn on the auto channel, then exits 0 so it never blocks
Claude. All failures are swallowed - a broken TTS setup must not break turns.
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_reader import client, config  # noqa: E402
from tts_reader.daemon import AUTO  # noqa: E402


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return

    cfg = config.load_config()
    if not cfg.get("enabled"):
        return  # opt-in: silent until `/tts on`

    client.send({
        "type": "speak",
        "channel": AUTO,
        "session_id": payload.get("session_id", "?"),
        "transcript_path": payload.get("transcript_path", ""),
        "cwd": payload.get("cwd", os.getcwd()),
        "mode": cfg.get("mode", "summary"),
        "request_ts": time.time(),
    })


if __name__ == "__main__":
    try:
        main()
    except Exception:  # never break a turn
        pass
    sys.exit(0)
