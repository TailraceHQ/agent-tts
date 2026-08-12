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
git clone <repository-url> ~/src/claude-code-tts
~/src/claude-code-tts/hosts/cursor/install.sh
~/src/claude-code-tts/scripts/run ~/src/claude-code-tts/scripts/tts_reader/cli.py on
```

`install.sh` merge-safely writes `~/.cursor/hooks.json` with this checkout’s
absolute paths. Unrelated hooks are preserved; re-running replaces only our
`stop` entry.

| Override | Effect |
| --- | --- |
| `CURSOR_HOOKS_FILE=/path/to/hooks.json` | Write somewhere other than `~/.cursor/hooks.json` |

Cursor reloads `hooks.json` automatically — no IDE restart required for the
hook registration itself.

### Manual

1. Clone this repository somewhere stable.
2. Copy or merge `hosts/cursor/hooks.json` into `~/.cursor/hooks.json` or
   `<project>/.cursor/hooks.json`.
3. Replace every `REPLACE_WITH_CHECKOUT` with the absolute clone path.
4. Enable TTS with the CLI (`on` below).

## Usage

Cursor has no Claude-style `/tts` slash packaging in this MVP. Use the CLI from
a terminal (or ask the agent to run it via the Shell tool):

```bash
CHECKOUT=~/src/claude-code-tts
TTS="$CHECKOUT/scripts/run $CHECKOUT/scripts/tts_reader/cli.py"

$TTS on          # enable automatic speech after completed turns
$TTS off         # disable + stop playback
$TTS summary     # speak lead paragraph only (default)
$TTS full        # speak the whole cleaned response
$TTS replay      # replay latest transcript for this cwd
$TTS replay full # one-shot full replay
$TTS stop        # stop current playback / clear queue
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
  `~/.agent-tts/last_speak.json` for CLI `replay` / `preview`.

Cancelled, errored, or incomplete stops stay silent.

### Optional skill note

Copy `hosts/cursor/skills/tts.md` into a Cursor rule/skill location you already
use so the agent knows the CLI entry point and subcommands.

## Transcripts

The shared reader accepts Cursor role-nested JSONL (`role` + `message.content`).
Replay/preview discovery order (shared with other hosts) prefers
`~/.agent-tts/last_speak.json`, then can fall back to
`~/.cursor/projects/<slug>/agent-transcripts/` for the current cwd.

If a future Cursor build changes the transcript shape, playback may stay silent
until the reader is updated — the turn itself is never blocked.

## Uninstall / disable

- Quick: `$TTS off` (keeps the hook; no speech).
- Remove the hook: delete our `stop` entry from `~/.cursor/hooks.json`, or
  restore a backup of that file.
- Data dir (shared): `~/.agent-tts/` — only remove if you also want Claude /
  Antigravity config cleared.

## See also

- [docs/multi-host.md](../../docs/multi-host.md) — shared decisions and host field map
- [README.md](../../README.md) — voices, backends, cloud providers, troubleshooting
