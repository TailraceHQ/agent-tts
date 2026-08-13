#!/bin/sh
# Merge-safe install of the Cursor stop hook, /tts command, and skill.
# Resolves this checkout's absolute path into ~/.cursor/{hooks.json,commands,skills}.
set -eu
HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/../.." && pwd)
if [ -n "${CURSOR_HOOKS_FILE:-}" ]; then
  exec "$ROOT/scripts/run" "$ROOT/scripts/tts_reader/cursor_install.py" \
    --checkout "$ROOT" --hooks-file "$CURSOR_HOOKS_FILE" "$@"
fi
"$ROOT/scripts/run" "$ROOT/scripts/tts_reader/cursor_install.py" \
  --checkout "$ROOT" "$@"
# Direct CLI on PATH so tts stop/skip/pause skip the agent round-trip.
"$ROOT/scripts/install-cli.sh" || true
