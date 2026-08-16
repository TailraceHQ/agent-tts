---
description: Control text-to-speech playback of agent responses
argument-hint: on|off|summary|closing|brief|full|replay [summary|closing|brief|full]|stop|skip|pause|resume|preview|status|migrate|voices|voice prose <name>|voice header <name>|wpm <n>|backend <auto|macos|windows|linux|cloud>|setup|cloud [setup]|cloud <provider|voice|key|env|region> <value>
allowed-tools: Bash(*)
---

!`"${CLAUDE_PLUGIN_ROOT}/scripts/run" "${CLAUDE_PLUGIN_ROOT}/scripts/tts_reader/cli.py" $ARGUMENTS`

The output above is the result of the TTS command. Relay it to the user verbatim (do not add commentary or take further action).
