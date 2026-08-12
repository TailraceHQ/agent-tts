# Cursor host packaging

Sample hooks and a lightweight skill that drive the shared TTS daemon from
Cursor Agent’s `stop` event.

## Install (recommended)

```bash
git clone <repository-url> ~/src/claude-code-tts
~/src/claude-code-tts/hosts/cursor/install.sh
~/src/claude-code-tts/scripts/run ~/src/claude-code-tts/scripts/tts_reader/cli.py on
```

`install.sh` merge-safely writes `~/.cursor/hooks.json` with this checkout’s
absolute paths (preserves unrelated hooks; re-running replaces only our stop
entry). Override the target file with `CURSOR_HOOKS_FILE=/path/to/hooks.json`.

Cursor reloads `hooks.json` automatically. The stop hook always prints `{}`
(never `followup_message`) and only speaks when `status == "completed"`.

## Install (manual)

1. Clone this repository somewhere stable.
2. Copy or merge `hosts/cursor/hooks.json` into `~/.cursor/hooks.json` or
   `<project>/.cursor/hooks.json`, replacing `REPLACE_WITH_CHECKOUT` with the
   absolute clone path.

## Commands / skill

Cursor has no Claude-style slash-command packaging in this MVP. Use the CLI:

```bash
CHECKOUT=~/src/claude-code-tts
"$CHECKOUT/scripts/run" "$CHECKOUT/scripts/tts_reader/cli.py" status
"$CHECKOUT/scripts/run" "$CHECKOUT/scripts/tts_reader/cli.py" on
"$CHECKOUT/scripts/run" "$CHECKOUT/scripts/tts_reader/cli.py" summary
"$CHECKOUT/scripts/run" "$CHECKOUT/scripts/tts_reader/cli.py" replay
"$CHECKOUT/scripts/run" "$CHECKOUT/scripts/tts_reader/cli.py" stop
```

Optional: copy `hosts/cursor/skills/tts.md` into a Cursor rule/skill location
you already use, so the agent knows how to invoke those subcommands.

## Transcript note

The hook passes Cursor’s `transcript_path` to the daemon and records it in
`~/.agent-tts/last_speak.json` for CLI replay. The shared reader accepts
role-nested Cursor JSONL (`role` + `message.content`). Replay/preview can also
discover `~/.cursor/projects/<slug>/agent-transcripts/` for the current cwd.
If a future Cursor build changes the format, playback may stay silent until a
dedicated reader or inline `text` path is added — the turn itself is never
blocked.
