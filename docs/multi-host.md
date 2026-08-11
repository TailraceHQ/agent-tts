# Multi-host TTS

This repo started as a Claude Code plugin. The core is host-agnostic so Cursor
and Google Antigravity adapters share one daemon, config, and sanitizer.

## Status

| Phase | Host | Status |
| --- | --- | --- |
| 0 | Decisions + SpeakRequest | Done |
| 1 | Shared core + Claude adapter wiring | Done |
| 2 | Cursor MVP packaging | Done (`hosts/cursor/`) |
| 3 | Antigravity MVP packaging | Done (`hosts/antigravity/` + root manifests) |

## Locked decisions

1. **Shared data directory:** canonical path is `~/.agent-tts/`. Override with
   `AGENT_TTS_DATA_DIR` when tests or a host need an explicit root. Claude’s
   former path was `~/.claude/claude-code-tts`. If the new dir does not exist
   but the legacy dir does, the legacy dir is kept (no copy) so existing config
   and a running daemon stay coherent. Fresh installs use `~/.agent-tts/`.
   Hook and CLI must always resolve the same path.

2. **Speak request shape:** adapters produce a shared `SpeakRequest`
   (`session_id`, `transcript_path`, optional `text`, `cwd`, `channel`,
   `mode`). The daemon prefers non-empty inline `text`; otherwise it reads
   `transcript_path` with the shared JSONL reader (Claude + Cursor role-nested).

3. **Opt-in remains:** `enabled` defaults to `false`.

4. **Pluggable readers:** Claude JSONL and common Cursor role-nested JSONL are
   handled by `transcript.py`. Antigravity transcript shape is still lightly
   validated — path is passed through; dedicated parsing can land when samples
   differ. Inline `text` remains available for hosts that can supply it.

## Host Stop fields

| Host | Session | Transcript | Workspace | Gate | Stdout |
| --- | --- | --- | --- | --- | --- |
| Claude Code | `session_id` | `transcript_path` | `cwd` | enabled + command suppression | (none required) |
| Cursor | `conversation_id` | `transcript_path` | `workspace_roots[0]` | `status == "completed"` | always `{}` |
| Antigravity | `conversationId` | `transcriptPath` | `workspacePaths[0]` | `fullyIdle` and not error | always `{}` |

## Packaging

- **Claude Code:** repo root `.claude-plugin/`, `hooks/hooks.json`, `commands/tts.md`,
  `scripts/tts_reader/hook.py` (unchanged install via `--plugin-dir`).
- **Cursor:** sample `hosts/cursor/hooks.json` → user `~/.cursor/hooks.json` or
  project `.cursor/hooks.json` with absolute checkout paths; entry
  `hook_cursor.py`. See `hosts/cursor/README.md`.
- **Antigravity:** preferred `agy plugin install <repo-root>` using root
  `plugin.json` / `hooks.json` / `skills/` (Stop → `hosts/antigravity/run`).
  Alternative: install `hosts/antigravity` and set `AGENT_TTS_ROOT`. See
  `hosts/antigravity/README.md`.

## Deferred

- Perfect Antigravity transcript parsing if format diverges from Claude/Cursor
- Cursor marketplace / one-click install
- Host-specific `/tts` replay transcript discovery outside Claude’s
  `~/.claude/projects/` layout (CLI still uses Claude paths for replay/preview)
