---
name: tts
description: Control shared agent text-to-speech (on/off/mode/stop/status/voices)
---

Run TTS subcommands through the plugin launcher (fail-open shared daemon):

```bash
"${ANTIGRAVITY_PLUGIN_ROOT}/run" cli $ARGUMENTS
```

If the plugin was installed from the repo root instead:

```bash
"${ANTIGRAVITY_PLUGIN_ROOT}/hosts/antigravity/run" cli $ARGUMENTS
```

Subcommands: `on`, `off`, `summary`, `full`, `replay [full|summary]`, `stop`,
`preview`, `status`, `voices`, `voice prose|header <name>`, `wpm <n>`,
`backend <auto|macos|windows|linux|cloud>`,
`cloud <provider|voice|key|region> <value>`.

Relay the CLI output to the user verbatim. Config lives under `~/.agent-tts/`
and is shared with Claude Code / Cursor. Starts disabled — use `on` once.
