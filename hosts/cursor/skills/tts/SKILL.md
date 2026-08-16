---
name: tts
description: >-
  Control shared agent TTS playback (on/off/summary/closing/brief/full/replay/stop/skip/pause/resume/preview/status/voices/wpm/backend).
  Use when the user asks to enable, disable, replay, stop, or configure TTS.
disable-model-invocation: true
---

Run the checkout CLI and relay stdout to the user **verbatim** (no commentary):

```bash
"REPLACE_WITH_CHECKOUT/scripts/run" "REPLACE_WITH_CHECKOUT/scripts/tts_reader/cli.py" <args>
```

Replace `<args>` with the user's subcommand and arguments (for example `replay full`, `stop`, `status`, `on`).

Useful subcommands: `on`, `off`, `summary`, `closing`, `brief`, `full`, `stop`,
`skip`, `pause`, `resume`, `status`, `voices`, `replay`, `replay full`,
`preview`, `wpm <n>`, `voice prose|header <name>`,
`backend <auto|macos|windows|linux|cloud>`,
`setup`, `cloud [setup]`,
`cloud <provider|voice|key|env|region> <value>`.

Config is shared under `~/.agent-tts/`. If you still have the legacy
`~/.claude/claude-code-tts/` directory, run `migrate` once (or let the first
CLI/hook call migrate automatically). TTS starts disabled; run `on` once.
