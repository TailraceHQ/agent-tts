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
agy plugin install ~/src/claude-code-tts
"${ANTIGRAVITY_PLUGIN_ROOT:-~/src/claude-code-tts}/hosts/antigravity/run" cli on
```

## Alternative: install only `hosts/antigravity`

After Antigravity copies this directory, `scripts/` is not inside the plugin
tree. Point `AGENT_TTS_ROOT` at the clone so `run` can find it:

```bash
export AGENT_TTS_ROOT=~/src/claude-code-tts
agy plugin install "$AGENT_TTS_ROOT/hosts/antigravity"
# Ensure AGENT_TTS_ROOT is visible to Antigravity hook subprocesses
"$AGENT_TTS_ROOT/hosts/antigravity/run" cli on
```

## Layout

```text
plugin.json          Manifest (also mirrored at repo root)
hooks.json           Stop → ./run hook
run                  Resolves checkout + launches hook_antigravity.py / cli.py
skills/tts/SKILL.md  Slash-style wrapper around cli.py
```
