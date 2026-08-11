"""Claude Code Stop-hook entrypoint.

Runs after every turn. Deliberately dumb and fast: maps the Claude Stop
payload through the adapter and signals the daemon. Exits 0 so it never
blocks Claude. All failures are swallowed.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_reader import config  # noqa: E402
from tts_reader.adapters import claude  # noqa: E402
from tts_reader.hook_common import run_stop_hook  # noqa: E402


def main() -> None:
    run_stop_hook(
        map_payload=claude.from_stop_payload,
        emit_empty_stdout=False,
        host="claude",
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never break a turn
        try:
            config.debug_log("claude_hook_exception", error=repr(exc))
        except Exception:
            pass
    sys.exit(0)
