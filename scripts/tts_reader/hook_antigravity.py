"""Antigravity Stop-hook entrypoint.

Always prints ``{}`` on stdout — never ``{"decision":"continue"}``. Fail-open.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_reader import config  # noqa: E402
from tts_reader.adapters import antigravity  # noqa: E402
from tts_reader.hook_common import run_stop_hook  # noqa: E402


def main() -> None:
    run_stop_hook(
        map_payload=antigravity.from_stop_payload,
        should_speak=antigravity.should_speak,
        emit_empty_stdout=True,
        host="antigravity",
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        try:
            config.debug_log("antigravity_hook_exception", error=repr(exc))
        except Exception:
            pass
        try:
            sys.stdout.write("{}\n")
            sys.stdout.flush()
        except Exception:
            pass
    sys.exit(0)
