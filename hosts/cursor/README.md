# Cursor host packaging

Sample hooks and a lightweight skill that drive the shared TTS daemon from
Cursor Agent’s `stop` event.

## Install (user-global)

1. Clone this repository somewhere stable (absolute path required):

   ```bash
   git clone <repository-url> ~/src/claude-code-tts
   ```

2. Copy or merge `hosts/cursor/hooks.json` into `~/.cursor/hooks.json`.
   Replace both `REPLACE_WITH_CHECKOUT` placeholders with the absolute clone
   path (example: `/Users/you/src/claude-code-tts`).

   Example finished entry:

   ```json
   {
     "version": 1,
     "hooks": {
       "stop": [
         {
           "command": "/Users/you/src/claude-code-tts/scripts/run /Users/you/src/claude-code-tts/scripts/tts_reader/hook_cursor.py",
           "timeout": 10
         }
       ]
     }
   }
   ```

3. Enable TTS once from a terminal (shared config under `~/.agent-tts/`):

   ```bash
   ~/src/claude-code-tts/scripts/run ~/src/claude-code-tts/scripts/tts_reader/cli.py on
   ```

Cursor reloads `hooks.json` automatically. The stop hook always prints `{}`
(never `followup_message`) and only speaks when `status == "completed"`.

## Install (project-local)

Copy the same `hooks.json` to `<project>/.cursor/hooks.json` with absolute
paths as above. Project hooks run with the project root as cwd; absolute paths
avoid relative-path surprises.

## Commands / skill

Cursor has no Claude-style slash-command packaging in this MVP. Use the CLI:

```bash
CHECKOUT=~/src/claude-code-tts
"$CHECKOUT/scripts/run" "$CHECKOUT/scripts/tts_reader/cli.py" status
"$CHECKOUT/scripts/run" "$CHECKOUT/scripts/tts_reader/cli.py" on
"$CHECKOUT/scripts/run" "$CHECKOUT/scripts/tts_reader/cli.py" summary
"$CHECKOUT/scripts/run" "$CHECKOUT/scripts/tts_reader/cli.py" stop
```

Optional: copy `hosts/cursor/skills/tts.md` into a Cursor rule/skill location
you already use, so the agent knows how to invoke those subcommands.

## Transcript note

The hook passes Cursor’s `transcript_path` to the daemon. The shared reader
accepts common role-nested Cursor JSONL (`role` + `message.content`). If a
future Cursor build changes the format, playback may stay silent until a
dedicated reader or inline `text` path is added — the turn itself is never
blocked.
