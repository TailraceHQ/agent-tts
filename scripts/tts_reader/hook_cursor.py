"""Cursor Agent stop-hook entrypoint.

Always prints ``{}`` on stdout (never ``followup_message``). Fail-open exit 0.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_reader import config  # noqa: E402
from tts_reader.adapters import cursor  # noqa: E402
from tts_reader.hook_common import run_stop_hook  # noqa: E402


def main() -> None:
    run_stop_hook(
        map_payload=cursor.from_stop_payload,
        should_speak=cursor.should_speak,
        emit_empty_stdout=True,
        host="cursor",
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        try:
            config.debug_log("cursor_hook_exception", error=repr(exc))
        except Exception:
            pass
        # Still emit noop stdout so Cursor does not treat a crash as a follow-up.
        try:
            sys.stdout.write("{}\n")
            sys.stdout.flush()
        except Exception:
            pass
    sys.exit(0)
