# Contributing to agent-tts

Thanks for helping improve **agent-tts**. This project is a host-agnostic TTS
plugin for Claude Code, Cursor, and Google Antigravity. Runtime code uses only
the Python standard library.

## Development setup

```bash
git clone https://github.com/TailraceHQ/agent-tts.git
cd agent-tts
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install "pytest>=7"
python -m pytest
```

Or install the optional dev extra from `pyproject.toml`:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

The suite uses fake speech processes and does not play audio. CI runs pytest on
Python 3.9 and 3.12 (see `.github/workflows/test.yml`).

### Manual smoke test

```bash
claude --plugin-dir "$PWD"
```

Then `/tts on`, ask a question, and check `/tts preview`, `/tts status`, and
`/tts replay`. Logs live under `~/.agent-tts/` (`daemon.log`, `debug.log`).

The player daemon is detached from the host process. After changing daemon
code, stop it so the next speak starts a fresh process:

```bash
data_dir="${AGENT_TTS_DATA_DIR:-$HOME/.agent-tts}"
test ! -f "$data_dir/daemon.pid" || kill "$(cat "$data_dir/daemon.pid")"
```

## Project layout

| Path | Role |
| --- | --- |
| `scripts/tts_reader/` | Shared core (daemon, CLI, sanitizer, engines, adapters) |
| `hosts/cursor/`, `hosts/antigravity/` | Host packaging and install helpers |
| `.claude-plugin/`, `hooks/`, `commands/` | Claude Code plugin wiring |
| `website/` | Fumadocs site (`pnpm --dir website dev`) |
| `tests/` | Unit tests (no audio required) |
| `docs/multi-host.md` | Multi-host design notes |

## Guidelines

- Keep runtime dependencies empty unless there is a strong reason; prefer the
  standard library.
- Prefer small, focused changes with tests for new behavior or bug fixes.
- Match existing style in nearby modules (naming, logging, error handling).
- Speech and hook failures should stay silent at the host boundary so a TTS
  problem never blocks an agent turn.
- Host-specific wiring belongs under `hosts/` or the matching adapter/hook;
  shared queue, sanitize, and engine logic stays in `scripts/tts_reader/`.

## Pull requests

1. Fork (or branch from `main`) and keep the change scoped to one concern.
2. Add or update tests under `tests/` when behavior changes.
3. Run `python -m pytest` locally before opening the PR.
4. Describe what changed and how you verified it (unit tests and/or manual
   `/tts` checks on the relevant host).

## Reporting issues

Include OS, Python version, host (Claude Code / Cursor / Antigravity), the
`/tts status` output (redact API keys), and relevant lines from
`~/.agent-tts/daemon.log` or `debug.log` when playback misbehaves.
