# Multi-host TTS

This repo ([TailraceHQ/claude-code-tts](https://github.com/TailraceHQ/claude-code-tts))
started as a Claude Code plugin and is in the process of moving to a
host-agnostic **agent-tts**. It already works with **Claude Code**, **Cursor**,
and **Google Antigravity**: the core is host-agnostic so all three adapters
share one daemon, config (`~/.agent-tts/`), and sanitizer.

## Status

| Phase | Host | Status |
| --- | --- | --- |
| 0 | Decisions + SpeakRequest | Done |
| 1 | Shared core + Claude adapter wiring | Done |
| 2 | Cursor packaging + install helper + discovery | Done (`hosts/cursor/`) |
| 3 | Antigravity packaging + install helper + step reader | Done (`hosts/antigravity/` + root manifests) |
| 4 | Cursor `/tts` command + skill install + auto-speak hardening | Done (`commands/`, `skills/tts/`, transcript fixtures) |

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
   `transcript_path` with the shared JSONL reader.

3. **Opt-in remains:** `enabled` defaults to `false`.

4. **Pluggable readers + discovery:** `transcript.py` reads Claude
   `type=assistant`, Cursor role-nested JSONL, and Antigravity step logs
   (`MODEL` + `PLANNER_RESPONSE` with string `content`). Replay/preview
   discovery order: `~/.agent-tts/last_speak.json` (written by Stop hooks),
   then Claude `~/.claude/projects/`, Cursor
   `~/.cursor/projects/<slug>/agent-transcripts/`, then Antigravity brain /
   project-local `transcript.jsonl`.

## Host Stop fields

| Host | Session | Transcript | Workspace | Gate | Stdout |
| --- | --- | --- | --- | --- | --- |
| Claude Code | `session_id` | `transcript_path` | `cwd` | enabled + command suppression | (none required) |
| Cursor | `conversation_id` | `transcript_path` | `workspace_roots[0]` | `status == "completed"` | always `{}` |
| Antigravity | `conversationId` | `transcriptPath` | `workspacePaths[0]` | `fullyIdle` and not error | always `{}` |

## Packaging

- **Claude Code:** repo root `.claude-plugin/`, `hooks/hooks.json`, `commands/tts.md`,
  `scripts/tts_reader/hook.py` (unchanged install via `--plugin-dir`).
- **Cursor:** run `hosts/cursor/install.sh` (merge-safe write to
  `~/.cursor/hooks.json`, plus `~/.cursor/commands/tts.md` and
  `~/.cursor/skills/tts/SKILL.md` with absolute checkout paths), or merge
  templates under `hosts/cursor/` manually. Entry: `hook_cursor.py`.
  **Install + usage:** [hosts/cursor/README.md](../hosts/cursor/README.md).
- **Antigravity:** preferred `agy plugin install <repo-root>` using root
  `plugin.json` / `hooks.json` / `skills/` (Stop → `hosts/antigravity/run`).
  Subdir install: `hosts/antigravity/install.sh` writes `.tts_root` so `run`
  finds `scripts/` without `AGENT_TTS_ROOT`.
  **Install + usage:** [hosts/antigravity/README.md](../hosts/antigravity/README.md).

## Known limitations

- Antigravity transcript parsing is based on documented step-log samples
  (MemPalace STDIN_SHAPE + public CLI tutorials), not a long-lived live corpus
  in CI. Unusual step `type` values or content shapes may stay silent until
  updated; turns are never blocked.
- Cursor marketplace / one-click store listing is out of scope (no real
  marketplace); `install.sh` is the supported path.
- Antigravity discovery without a prior Stop hook picks the newest brain
  `transcript.jsonl` globally when no project-local file exists — may be
  ambiguous across concurrent conversations.
- Repo rename / Claude Code marketplace listing remain separate work.
