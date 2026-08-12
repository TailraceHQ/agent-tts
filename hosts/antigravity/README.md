# Antigravity host packaging

Stop hook speaks only when `fullyIdle` is true and termination is not a clear
error. Stdout is always `{}` — never `{"decision":"continue"}`.

## Preferred: install the whole repo checkout

`agy plugin install` copies the directory you give it. Installing the **repo
root** keeps `scripts/` next to this host package so the `run` shim finds
`tts_reader` without extra environment variables.

Root manifests (`plugin.json`, `hooks.json`, `skills/`) point at
`hosts/antigravity/run`. Claude Code packaging is unchanged
(`.claude-plugin/`, `hooks/hooks.json`, `commands/`).

```bash
git clone <repository-url> ~/src/claude-code-tts
# optional helper (also records checkout markers):
~/src/claude-code-tts/hosts/antigravity/install.sh root
# or directly:
agy plugin install ~/src/claude-code-tts
~/src/claude-code-tts/hosts/antigravity/run cli on
```

## Alternative: install only `hosts/antigravity`

Run the helper once from the clone so `run` can find `scripts/` after Antigravity
copies this directory (writes `.tts_root` + `~/.agent-tts/checkout`):

```bash
~/src/claude-code-tts/hosts/antigravity/install.sh subdir
# equivalent manual flow:
#   echo "$PWD" > hosts/antigravity/.tts_root   # from repo root
#   agy plugin install hosts/antigravity
"${ANTIGRAVITY_PLUGIN_ROOT:-...}/run" cli on
```

You can still set `AGENT_TTS_ROOT` to the clone if you prefer an env override.

## Layout

```text
plugin.json          Manifest (also mirrored at repo root)
hooks.json           Stop → ./run hook
run                  Resolves checkout + launches hook_antigravity.py / cli.py
install.sh           Writes .tts_root / checkout markers; optional agy install
skills/tts/SKILL.md  Slash-style wrapper around cli.py
```

## Transcript note

Antigravity transcripts are step-log JSONL (`source` / `type` / `content`).
The reader speaks the last `MODEL` + `PLANNER_RESPONSE` with non-empty
`content`, skipping tool-only planner rows and tool-result steps. The Stop
hook also records `transcriptPath` for `/tts replay` via `last_speak.json`.
