# Cursor: install and usage

Drive the shared TTS daemon from Cursor Agent’s `stop` event. Config and
playback are shared with Claude Code and Antigravity under `~/.agent-tts/`.

TTS starts **disabled**. Enable it once after install.

## Prerequisites

Same as the main [README](../../README.md): Python 3.9+, a local speech engine
(`say` / Windows SAPI / `espeak-ng`), and a stable clone of this repo.

## Install

### Recommended (`install.sh`)

```bash
git clone https://github.com/TailraceHQ/agent-tts.git ~/src/agent-tts
~/src/agent-tts/hosts/cursor/install.sh
~/src/agent-tts/scripts/run ~/src/agent-tts/scripts/tts_reader/cli.py on
```

`install.sh` is merge-safe and idempotent. It writes:

| Target | Purpose |
| --- | --- |
| `~/.cursor/hooks.json` | Stop hook → `hook_cursor.py` (absolute checkout paths) |
| `~/.cursor/commands/tts.md` | `/tts` slash command → checkout `cli.py` |
| `~/.cursor/skills/tts/SKILL.md` | Explicit `/tts` skill (same CLI) |

Unrelated hooks are preserved; re-running replaces only our stop entry and
rewrites the command/skill templates.

| Override | Effect |
| --- | --- |
| `CURSOR_HOOKS_FILE=/path/to/hooks.json` | Write hooks somewhere other than `~/.cursor/hooks.json` |

Cursor reloads `hooks.json` automatically. New slash commands/skills may need
a new Agent chat (or Cursor reload) before `/tts` appears.

### Manual

1. Clone this repository somewhere stable.
2. Copy or merge `hosts/cursor/hooks.json` into `~/.cursor/hooks.json` or
   `<project>/.cursor/hooks.json`.
3. Copy `hosts/cursor/commands/tts.md` → `~/.cursor/commands/tts.md` and
   `hosts/cursor/skills/tts/SKILL.md` → `~/.cursor/skills/tts/SKILL.md`.
4. Replace every `REPLACE_WITH_CHECKOUT` with the absolute clone path.
5. Enable TTS with `/tts on` (or the CLI below).

## Usage

### Slash command (preferred)

After install, in Agent chat:

```text
/tts on
/tts status
/tts replay full
/tts stop
/tts off
```

The command runs this checkout’s CLI and relays stdout verbatim. For `stop`,
`skip`, `pause`, and `resume`, use the direct CLI below — slash commands wait
on the model.

### CLI (same entry point)

```bash
# after install.sh, or: ~/src/agent-tts/scripts/install-cli.sh
tts on
tts closing     # last paragraph (usually the answer)
tts skip
tts pause
tts resume
```

```bash
CHECKOUT=~/src/agent-tts
TTS="$CHECKOUT/scripts/tts"

$TTS on          # enable automatic speech after completed turns
$TTS off         # disable + stop playback
$TTS summary     # speak lead paragraph only (default)
$TTS closing     # speak last paragraph only
$TTS brief       # speak first sentence
$TTS full        # speak the whole cleaned response
$TTS replay      # replay latest transcript for this cwd
$TTS replay full # one-shot full replay
$TTS stop        # stop current playback / clear queue
$TTS skip        # skip current utterance, continue this response
$TTS pause       # hold playback; $TTS resume continues
$TTS preview     # print what would be spoken (no audio)
$TTS status      # show active config
$TTS voices      # list selectable voices
$TTS voice prose Samantha
$TTS voice header Fred
$TTS wpm 180
$TTS backend auto   # or macos | windows | linux | cloud
```

Cloud voice options match the main README (`cloud provider|voice|key|region`).

### When speech runs

The stop hook:

- Always prints `{}` (never `followup_message`) so it cannot steer the agent.
- Speaks only when the hook payload has `status == "completed"`.
- Passes Cursor’s `transcript_path` into the shared daemon and records it in
  `~/.agent-tts/last_speak.json` for CLI / `/tts replay` / `preview`.
- Reader prefers the last **text-only** assistant message after the latest user
  turn (skips `text`+`tool_use` preambles); polls briefly for `turn_ended` when
  only a preamble is present yet.

Cancelled, errored, or incomplete stops stay silent.

## Transcripts

The shared reader accepts Cursor role-nested JSONL (`role` + `message.content`)
and ignores roleless status lines such as `{"type":"turn_ended"}`.
Replay/preview discovery order (shared with other hosts) prefers
`~/.agent-tts/last_speak.json`, then can fall back to
`~/.cursor/projects/<slug>/agent-transcripts/` for the current cwd.

Fixture used in CI: `tests/fixtures/cursor/agent_transcript.jsonl`.

If a future Cursor build changes the transcript shape, playback may stay silent
until the reader is updated — the turn itself is never blocked.

## Uninstall / disable

- Quick: `/tts off` (keeps the hook; no speech).
- Remove the hook: delete our `stop` entry from `~/.cursor/hooks.json`, or
  restore a backup of that file.
- Remove `/tts`: delete `~/.cursor/commands/tts.md` and
  `~/.cursor/skills/tts/`.
- Data dir (shared): `~/.agent-tts/` — only remove if you also want Claude /
  Antigravity config cleared.

## See also

- [docs/multi-host.md](../../docs/multi-host.md) — shared decisions and host field map
- [README.md](../../README.md) — voices, backends, cloud providers, troubleshooting
