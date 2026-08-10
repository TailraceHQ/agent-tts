# Multi-host TTS (Phase 0 decisions)

This repo started as a Claude Code plugin. The core is being made host-agnostic
so Cursor and Google Antigravity adapters can share one daemon, config, and
sanitizer. Full packaging for those hosts is deferred.

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
   `transcript_path` with the existing Claude JSONL reader.

3. **Opt-in remains:** `enabled` defaults to `false`.

4. **Pluggable readers:** Cursor/Antigravity transcript formats were not
   captured live in this spike. Host adapters map Stop stdin fields only;
   Claude’s JSONL reader is preserved. Host-specific readers land when sample
   transcripts exist.

## Documented host Stop fields (not yet packaged)

| Host | Session | Transcript | Workspace | Other |
| --- | --- | --- | --- | --- |
| Claude Code | `session_id` | `transcript_path` | `cwd` | `hook_event_name` |
| Cursor | `conversation_id` | `transcript_path` | `workspace_roots` | `status`, `hook_event_name` |
| Antigravity | `conversationId` | `transcriptPath` | `workspacePaths` | `fullyIdle`, `terminationReason` |

Stub mappers live under `scripts/tts_reader/adapters/` (`cursor.py`,
`antigravity.py`). Claude remains the only wired Stop hook.
