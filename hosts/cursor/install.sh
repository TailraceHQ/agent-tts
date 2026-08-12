#!/bin/sh
# Merge-safe install of the Cursor stop hook into ~/.cursor/hooks.json
# (or CURSOR_HOOKS_FILE). Resolves this checkout's absolute path.
set -eu
HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/../.." && pwd)
if [ -n "${CURSOR_HOOKS_FILE:-}" ]; then
  exec "$ROOT/scripts/run" "$ROOT/scripts/tts_reader/cursor_install.py" \
    --checkout "$ROOT" --hooks-file "$CURSOR_HOOKS_FILE" "$@"
fi
exec "$ROOT/scripts/run" "$ROOT/scripts/tts_reader/cursor_install.py" \
  --checkout "$ROOT" "$@"