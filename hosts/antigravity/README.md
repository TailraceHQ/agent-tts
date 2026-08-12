# Antigravity: install and usage

Stop-hook adapter for Google Antigravity. Speaks only when the turn is
`fullyIdle` and termination is not a clear error. Stdout is always `{}` —
never `{"decision":"continue"}`.

Config and playback are shared with Claude Code and Cursor under
`~/.agent-tts/`. TTS starts **disabled**. Enable it once after install.

## Prerequisites

Same as the main [README](../../README.md): Python 3.9+, a local speech engine,
Git, and the Antigravity CLI (`agy`) if you use the preferred install path.

## Install

### Preferred: whole repo checkout

`agy plugin install` copies the directory you give it. Installing the **repo
root** keeps `scripts/` next to this host package so the `run` shim finds
`tts_reader` without extra environment variables.

Root manifests (`plugin.json`, `hooks.json`, `skills/`) point at
`hosts/antigravity/run`. Claude Code packaging is unchanged
(`.claude-plugin/`, `hooks/hooks.json`, `commands/`).

```bash
git clone https://github.com/TailraceHQ/agent-tts.git ~/src/agent-tts

# optional helper (records checkout markers, then runs agy):
~/src/agent-tts/hosts/antigravity/install.sh root

# or install directly:
agy plugin install ~/src/agent-tts

~/src/agent-tts/hosts/antigravity/run cli on
```

### Alternative: `hosts/antigravity` only

Run the helper once from the clone so `run` can find `scripts/` after
Antigravity copies this directory (writes `.tts_root` and
`~/.agent-tts/checkout`):

```bash
~/src/agent-tts/hosts/antigravity/install.sh subdir
"${ANTIGRAVITY_PLUGIN_ROOT}/run" cli on
```

Equivalent manual flow:

```bash
# from repo root
echo "$PWD" > hosts/antigravity/.tts_root
agy plugin install hosts/antigravity
```

You can also set `AGENT_TTS_ROOT` to the clone absolute path instead of using
`.tts_root`.

### `install.sh` modes

| Mode | Behavior |
| --- | --- |
| `subdir` (default) | Write `.tts_root` + data-dir marker; `agy plugin install hosts/antigravity` |
| `root` / `repo` | Write markers; `agy plugin install` the repo root |
| `marker-only` | Write markers only (no `agy`) |

If `agy` is not on `PATH`, the script still writes markers and prints the
manual install command.

## Usage

### Via skill / slash-style command

After plugin install, Antigravity’s `skills/tts` wraps the CLI:

```text
/tts on
/tts off
/tts summary
/tts full
/tts replay
/tts replay full
/tts stop
/tts preview
/tts status
/tts voices
/tts voice prose Samantha
/tts wpm 180
/tts backend auto
```

The skill runs:

```bash
"${ANTIGRAVITY_PLUGIN_ROOT}/run" cli <subcommand...>
```

If you installed from the repo root, that resolves through
`hosts/antigravity/run`. Subdir installs use `"${ANTIGRAVITY_PLUGIN_ROOT}/run"`
directly.

### Via CLI (same subcommands)

From the checkout, without relying on the skill:

```bash
CHECKOUT=~/src/agent-tts
"$CHECKOUT/hosts/antigravity/run" cli on
"$CHECKOUT/hosts/antigravity/run" cli status
"$CHECKOUT/hosts/antigravity/run" cli replay
"$CHECKOUT/hosts/antigravity/run" cli stop
```

Cloud options match the main README (`cloud provider|voice|key|region`).

### When speech runs

The Stop hook:

- Always prints `{}` so it cannot continue or otherwise steer the agent.
- Speaks only when `fullyIdle` is true and termination is not a clear error.
- Passes `conversationId`, `transcriptPath`, and `workspacePaths[0]` into the
  shared daemon, and records the transcript in `~/.agent-tts/last_speak.json`
  for `/tts replay`.

### Layout

```text
plugin.json          Manifest (also mirrored at repo root)
hooks.json           Stop → ./run hook
run                  Resolves checkout + launches hook_antigravity.py / cli.py
install.sh           Writes .tts_root / checkout markers; optional agy install
skills/tts/SKILL.md  Slash-style wrapper around cli.py
```

`run` resolution order: `AGENT_TTS_ROOT` → whole-repo
`ANTIGRAVITY_PLUGIN_ROOT` → `.tts_root` → `~/.agent-tts/checkout` → legacy
Claude data-dir checkout → relative `../../scripts`.

## Transcripts

Antigravity transcripts are step-log JSONL (`source` / `type` / `content`).
The reader speaks the last `MODEL` + `PLANNER_RESPONSE` with non-empty
`content`, skipping tool-only planner rows and tool-result steps.

Discovery without a prior Stop hook may pick the newest brain
`transcript.jsonl` globally when no project-local file exists — that can be
ambiguous across concurrent conversations. Prefer enabling TTS and letting Stop
write `last_speak.json`.

Unusual step `type` values or content shapes may stay silent until the reader
is updated; turns are never blocked.

## Uninstall / disable

- Quick: `/tts off` or `run cli off`.
- Remove the plugin via Antigravity’s usual plugin uninstall flow.
- Data dir (shared): `~/.agent-tts/` — only remove if you also want Claude /
  Cursor config cleared.

## See also

- [docs/multi-host.md](../../docs/multi-host.md) — shared decisions and host field map
- [README.md](../../README.md) — voices, backends, cloud providers, troubleshooting
