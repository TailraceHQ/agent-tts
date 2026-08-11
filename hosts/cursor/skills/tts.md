---
description: Control shared agent TTS playback (on/off/mode/stop/status)
---

This checkout exposes a CLI (not a Cursor slash command). From a terminal, or
via the Shell tool with the absolute clone path:

```bash
CHECKOUT=/absolute/path/to/claude-code-tts
"$CHECKOUT/scripts/run" "$CHECKOUT/scripts/tts_reader/cli.py" <subcommand>
```

Useful subcommands: `on`, `off`, `summary`, `full`, `stop`, `status`, `voices`,
`replay`, `preview`, `wpm <n>`, `voice prose|header <name>`,
`backend <auto|macos|windows|linux|cloud>`.

Config is shared under `~/.agent-tts/` with Claude Code and Antigravity. TTS
starts disabled; run `on` once. Relay CLI output to the user verbatim.
