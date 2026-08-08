---
description: Control text-to-speech playback of Claude's responses
argument-hint: on|off|summary|full|replay|stop|preview|status|voices|voice prose <name>|voice header <name>|wpm <n>
allowed-tools: Bash(python3 *)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tts_reader/cli.py" $ARGUMENTS`

The output above is the result of the TTS command. Relay it to the user verbatim (do not add commentary or take further action).
