#!/bin/sh
# Register this checkout as a Claude Code user-scope plugin so TTS loads in
# every session. ``claude --plugin-dir`` only lasts until you quit.
set -eu
HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/../.." && pwd)

if ! command -v claude >/dev/null 2>&1; then
  echo "agent-tts: claude CLI not found on PATH" >&2
  exit 1
fi

claude plugin marketplace add "$ROOT" --scope user
claude plugin install tts@tailrace -s user
"$ROOT/scripts/install-cli.sh" || true
echo "TTS plugin enabled for every Claude Code session (tts@tailrace)."
echo "After pulling plugin changes: claude plugin update tts@tailrace"
echo "Then in a session: /tts:tts on"
