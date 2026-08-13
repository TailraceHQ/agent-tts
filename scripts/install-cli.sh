#!/bin/sh
# Symlink the direct `tts` CLI onto PATH so stop/skip/pause/replay do not
# go through an agent slash command.
set -eu
HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/.." && pwd)
SRC="$ROOT/scripts/tts"
BIN="${AGENT_TTS_BIN_DIR:-$HOME/.local/bin}"

if [ ! -f "$SRC" ]; then
  echo "agent-tts: missing $SRC" >&2
  exit 1
fi
mkdir -p "$BIN"
ln -sf "$SRC" "$BIN/tts"
echo "Linked $BIN/tts -> $SRC"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *)
    echo "Add $BIN to PATH if 'tts' is not found, e.g.:"
    echo "  export PATH=\"$BIN:\$PATH\""
    ;;
esac
echo "Try: tts status"
