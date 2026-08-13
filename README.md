# agent-tts

[![Version](https://img.shields.io/badge/version-0.2.0-blue)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.9+-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-host-191919)](docs/multi-host.md)
[![Cursor](https://img.shields.io/badge/Cursor-host-000000)](hosts/cursor/README.md)
[![Antigravity](https://img.shields.io/badge/Antigravity-host-4285F4)](hosts/antigravity/README.md)
[![License: MIT](https://img.shields.io/github/license/TailraceHQ/agent-tts)](LICENSE)
[![Tests](https://img.shields.io/github/actions/workflow/status/TailraceHQ/agent-tts/test.yml?branch=main&label=tests)](https://github.com/TailraceHQ/agent-tts/actions/workflows/test.yml)

A cross-platform plugin that reads an agent's completed responses aloud on
**macOS, Windows, and Linux**. It cleans up Markdown before speaking, can use
different voices for prose and headings, and coordinates playback across
multiple sessions so they do not talk over one another.

**agent-tts** is host-agnostic: it works with **Claude Code**, **Cursor**, and
**Google Antigravity** through a shared daemon, config (`~/.agent-tts/`), and
sanitizer. See [docs/multi-host.md](docs/multi-host.md) for host wiring, and
the per-host guides under [`hosts/`](hosts/).

The plugin is opt-in and uses only Python's standard library. By default it
drives each operating system's built-in speech engine, so nothing is sent to an
external service. Optionally, you can plug in your own voice through a cloud
provider (ElevenLabs, OpenAI, or Azure) - see [Cloud voices](#cloud-voices).

## Prerequisites

- Claude Code with plugin support
- Python 3.9 or newer (`python3 --version`, or `python --version` on Windows)
- A speech engine for your platform (all built in / freely installable):
  - **macOS** - the built-in `say` command (nothing to install)
  - **Windows** - PowerShell with SAPI (`System.Speech`), present by default
  - **Linux** - `espeak-ng` (preferred) or `spd-say` from speech-dispatcher,
    e.g. `sudo apt install espeak-ng`
- Git, if installing from a source checkout

Quickly verify the local speech engine before installing:

```bash
# macOS
say "Text to speech is working"
# Linux
espeak-ng "Text to speech is working"
```

```powershell
# Windows (PowerShell)
Add-Type -AssemblyName System.Speech
(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("Text to speech is working")
```

## Install

This repository is currently a standalone plugin, not a Claude Code marketplace.
Clone it, then load the checkout directly:

```bash
git clone https://github.com/TailraceHQ/agent-tts.git ~/src/agent-tts
claude --plugin-dir ~/src/agent-tts
```

`--plugin-dir` loads the plugin for that Claude Code process. Use an absolute
path if the shell expands `~` differently in your setup. To load it every time,
add a shell function to `~/.zshrc`:

```bash
claude() {
  command claude --plugin-dir "$HOME/src/agent-tts" "$@"
}
```

Restart the shell after adding the function. If you already wrap the `claude`
command, add the `--plugin-dir` argument to that wrapper instead.

The plugin starts disabled. In Claude Code, enable it with:

```text
/tts on
```

Configuration is shared by sessions using the same plugin data directory, so
you only need to enable it once.

## Commands

| Command | Effect |
| --- | --- |
| `/tts on` | Enable automatic speech after completed responses |
| `/tts off` | Disable future automatic speech, stop current playback, and clear the queue |
| `/tts summary` | Speak only the first prose paragraph (default) |
| `/tts full` | Speak the entire cleaned response |
| `/tts replay [full\|summary]` | Replay the latest response for the current working directory, optionally overriding the configured mode for just this replay |
| `/tts stop` | Stop current playback and clear the queue |
| `/tts preview` | Print exactly what would be spoken, including voice assignments, without playing audio |
| `/tts voice prose <name>` | Select the voice used for normal prose |
| `/tts voice header <name>` | Select a second voice for headings and blockquotes |
| `/tts wpm <number>` | Set the speaking rate in words per minute |
| `/tts voices` | List voices the active backend can select |
| `/tts backend <auto\|macos\|windows\|linux\|cloud>` | Choose the speech engine (`auto` picks your OS's built-in engine) |
| `/tts cloud provider <elevenlabs\|openai\|azure>` | Choose the cloud provider (used when backend is `cloud`) |
| `/tts cloud voice <id>` | Set the provider voice id |
| `/tts cloud key <api-key>` | Store the provider API key (env var preferred, see below) |
| `/tts cloud region <region>` | Set the region (Azure only) |
| `/tts status` | Show the active configuration |

Voice names may contain spaces:

```text
/tts voice prose Samantha
/tts voice header Daniel
/tts wpm 190
/tts full
/tts preview
```

## Configuration

The defaults are:

```json
{
  "enabled": false,
  "mode": "summary",
  "prose_voice": null,
  "header_voice": null,
  "wpm": 175,
  "backend": "auto",
  "cloud": {
    "provider": "elevenlabs",
    "voice": null,
    "api_key": null,
    "region": null
  }
}
```

Use the `/tts` commands rather than editing this file where possible. A `null`
prose voice tells the active backend to use its system default voice. A `null`
header voice uses the prose voice, which disables the audible prose/header
distinction. There is not currently a reset-voice command; set either value
back to `null` in `config.json` when you need to return to these defaults.

`backend` selects the speech engine: `auto` (the default) resolves to your
operating system's built-in engine, or force `macos` / `windows` / `linux` /
`cloud`. The `cloud` block is only used when `backend` is `cloud`.

Configuration and daemon state are stored under:

```text
~/.agent-tts/
  config.json
  last_speak.json last Stop-hook transcript path (CLI replay/preview)
  daemon.log
  daemon.pid
  daemon.port     port + auth token for the loopback control channel
  debug.log
  audio/          synthesized clips (cloud backend only; auto-pruned)
```

Override with `AGENT_TTS_DATA_DIR` if needed. If `~/.agent-tts` does not exist
but the legacy Claude path `~/.claude/claude-code-tts` does, that legacy
directory is **migrated** (copied) into `~/.agent-tts` automatically on first
use. Live daemon runtime files (`daemon.pid` / `daemon.port` / `daemon.sock` /
`daemon.log`) are skipped so a new daemon starts under the canonical path; the
legacy directory is left in place with a `MIGRATED_TO_AGENT_TTS` marker. Run
`/tts migrate` to migrate explicitly, or `/tts status` to confirm `data_dir`.
Fresh installs use `~/.agent-tts` directly.

This path is shared by the Stop hook and `/tts` CLI rather than derived from
`$CLAUDE_PLUGIN_DATA`: Claude Code only injects that env var into hook
subprocesses, not into the inline `!` bash that runs the `/tts` command.
Keying config off it split state across two directories and silently broke
automatic playback. Pinning both entry points to the same resolved path keeps
them in sync. The daemon exits after 30 minutes without queued or active work
and starts again automatically when needed.

The core is host-agnostic (shared daemon + adapters). Claude Code remains the
primary packaged host; Cursor and Antigravity MVPs live under `hosts/`. See
[docs/multi-host.md](docs/multi-host.md).

### Cursor

```bash
git clone https://github.com/TailraceHQ/agent-tts.git ~/src/agent-tts
~/src/agent-tts/hosts/cursor/install.sh
# then in Agent chat: /tts on
# (or) ~/src/agent-tts/scripts/run ~/src/agent-tts/scripts/tts_reader/cli.py on
```

`install.sh` merge-safely writes absolute checkout paths into
`~/.cursor/hooks.json`, and installs `/tts` as `~/.cursor/commands/tts.md`
plus `~/.cursor/skills/tts/SKILL.md`. Full install, usage, and uninstall notes:
[hosts/cursor/README.md](hosts/cursor/README.md).

### Antigravity

Preferred (whole checkout so `scripts/` is available after install):

```bash
agy plugin install /absolute/path/to/agent-tts
/absolute/path/to/agent-tts/hosts/antigravity/run cli on
```

Or `hosts/antigravity/install.sh subdir` (writes a `.tts_root` marker so the
`run` shim finds `scripts/` without `AGENT_TTS_ROOT`). Full install, `/tts`
usage, and uninstall notes: [hosts/antigravity/README.md](hosts/antigravity/README.md).

## Voice quality (macOS)

Audio quality comes from the installed macOS voice, not from this plugin.
Run `/tts voices` to see the voices that `say -v ?` exposes, then try them in a
terminal before configuring the plugin:

```bash
say -v Samantha -r 175 "This is a voice test"
```

Additional and higher-quality voices can be downloaded in **System Settings →
Accessibility → Spoken Content → System Voice** (the exact labels vary by
macOS version). Enhanced or Premium voices generally sound more natural but use
more disk space. After downloading one, run `/tts voices` again.

### Why can't I select a Siri voice?

Apple does not expose Siri voices as named voices to the `say` command, so they
usually do not appear in `/tts voices` and `/tts voice prose Siri ...` will not
work. On recent macOS versions, `say` may use a downloaded Siri voice when that
voice is selected as the system voice and no explicit `-v` voice is supplied.
To try that behavior:

1. Select the Siri voice as the System Voice in Accessibility settings.
2. Leave `prose_voice` unset (`null` in `config.json`).
3. Do not configure a named prose voice with `/tts voice prose`.

This behavior is controlled by macOS and varies by release. Siri voices still
cannot reliably be selected by name, and assigning separate Siri voices to the
prose and header roles is not supported.

## Cloud voices

To use your own voice from a hosted provider instead of the built-in OS engine,
switch the backend to `cloud` and pick a provider and voice. Each response is
synthesized over HTTPS and played locally.

```text
/tts backend cloud
/tts cloud provider elevenlabs
/tts cloud voice 21m00Tcm4TlvDq8ikWAM
```

Supported providers and their voice ids:

| Provider | `provider` value | Voice id example | Notes |
| --- | --- | --- | --- |
| ElevenLabs | `elevenlabs` | `21m00Tcm4TlvDq8ikWAM` (Rachel) | `/tts voices` lists your account's voices when a key is set |
| OpenAI | `openai` | `alloy`, `nova`, … | `/tts wpm` maps to the API `speed` parameter |
| Azure | `azure` | `en-US-JennyNeural` | also requires `/tts cloud region <region>` |

**API keys.** The key is read from an environment variable first, falling back
to what you store with `/tts cloud key`. Prefer the environment variable so the
key never lands in `config.json`:

| Provider | Environment variable |
| --- | --- |
| ElevenLabs | `ELEVENLABS_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Azure | `AZURE_SPEECH_KEY` |

Playback of synthesized audio needs a player: macOS uses `afplay` (built in),
Linux uses `ffplay`/`mpg123`/`aplay`/`paplay` (install one, e.g. `ffmpeg`), and
Windows uses PowerShell's media APIs. If a cloud request fails or no API key is
found, the plugin stays silent for that turn rather than raising - check
`debug.log` if a cloud voice is unexpectedly quiet.

## How it works

Claude Code runs the plugin's `Stop` hook after a turn. The hook itself does
not read the transcript - it just signals a background player daemon, which
does the (slightly slower) work of reading the transcript, converting it into
an utterance queue, and speaking each utterance through the active backend
(the OS engine or a cloud provider). That split keeps the hook fast so it never
delays the turn from returning control to you.

By the time the hook fires, the turn's final assistant message is already on
disk, so the daemon normally finds it on the very first read. If the
transcript write is still lagging for some reason, the daemon polls for up to
three seconds before giving up rather than speaking nothing.

Before playback, the sanitizer:

- strips Markdown emphasis and link destinations;
- turns code blocks and tables into short spoken pointers instead of reading
  their contents character by character;
- expands common function names, identifiers, file references, and line
  numbers into more natural speech;
- assigns headings and blockquotes to the header voice; and
- emits each list item as a separate utterance.

In summary mode, only the first prose paragraph is spoken. If there is no prose
paragraph, the first available block is used.

## Multiple sessions and channels

Sessions using the same plugin data directory share one daemon and therefore
one speaker queue. Only one `say` process plays at a time.

- A new automatic response from the **same session** replaces that session's
  older queued automatic response. If the older response is currently playing,
  it is interrupted.
- A response from a **different session** waits in the queue. It never
  interrupts the session currently speaking.
- When playback changes to another session, the daemon announces
  `"<working-directory> speaking"` using the prose voice.
- Settings such as enabled state, mode, voices, and rate are global to the
  shared data directory, not per session.

“Channel” means a queue category inside the daemon; it does not mean a left or
right audio channel:

- `auto` is used by the `Stop` hook. Newer auto jobs may replace older auto jobs
  from the same session.
- `replay` is used by `/tts replay`. A replay is not cancelled by the automatic
  `Stop` event caused by the replay command's own turn.

Every `/tts` command's own echoed confirmation text (e.g. "Replaying last
response.", "TTS enabled.") is excluded from the `auto` channel - it is
plugin meta-output, not a Claude response, and for `/tts replay` in
particular auto-speaking it on top of the actual replay is what used to make
a single replay audibly play more than once.

`/tts stop` and `/tts off` currently act globally: they interrupt whatever is
playing, regardless of which session started it, and clear the entire pending
queue across all sessions.

## Text transforms

| Input | Spoken |
| --- | --- |
| `build()` | “the build function” |
| `load_config` | “the load config function” |
| `loadConfig()` | “load config function” |
| `` `modes.py:12` `` | “mode dot pi, line 12” |
| `:300` | “line 300” |
| `~20` | “about 20” |
| `**bold**`, `*italic*` | markers removed |
| fenced code block | “see codeblock below” |
| Markdown table | “see table below” |
| heading or blockquote | assigned to the header voice |

The built-in file-extension pronunciation map is
`DEFAULT_PRONUNCIATION` in `scripts/tts_reader/sanitize.py`.

## Update

Because the plugin is loaded from a Git checkout, update that checkout:

```bash
cd ~/src/agent-tts
git pull --ff-only
```

Start a new Claude Code process afterward. During plugin development,
`/reload-plugins` can reload plugin components. The player daemon is detached
from Claude Code, however, so restarting Claude Code does not replace an already
running daemon. It exits automatically after 30 idle minutes. To apply daemon
code changes immediately, stop it after playback has finished:

```bash
data_dir="${AGENT_TTS_DATA_DIR:-$HOME/.agent-tts}"
test ! -f "$data_dir/daemon.pid" || kill "$(cat "$data_dir/daemon.pid")"
```

The next response starts the updated daemon automatically.

## Uninstall

1. Run `/tts off` to stop playback and disable the plugin.
2. Remove `--plugin-dir ~/src/agent-tts` from your Claude Code command or
   remove the shell function shown above.
3. Close Claude Code sessions that loaded the plugin.
4. Stop the detached daemon so previously queued responses cannot continue:

   ```bash
   data_dir="${AGENT_TTS_DATA_DIR:-$HOME/.agent-tts}"
   test ! -f "$data_dir/daemon.pid" || kill "$(cat "$data_dir/daemon.pid")"
   ```

5. Delete the source checkout:

   ```bash
   rm -rf ~/src/agent-tts
   ```

6. Optionally remove saved settings and logs:

   ```bash
   rm -rf "$data_dir"
   # and, if present after migration:
   # rm -rf ~/.claude/claude-code-tts
   ```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, guidelines, and pull requests.

Clone the repository, create a virtual environment, and install the test
dependency:

```bash
cd ~/src/agent-tts
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "pytest>=7"
python -m pytest
```

The test suite uses fake speech processes, so it does not produce audio. For a
manual end-to-end test:

```bash
claude --plugin-dir "$PWD"
```

Then run `/tts on`, ask Claude a question, and use `/tts preview`, `/tts status`,
and `/tts replay` to inspect the result. Runtime logs are in
`~/.agent-tts/daemon.log` (plus `debug.log` for hook/daemon tracing).

Project layout:

```text
.claude-plugin/plugin.json   Claude Code plugin manifest
hooks/hooks.json             Claude Stop hook registration
commands/tts.md              Claude /tts slash command
plugin.json                  Antigravity plugin manifest (repo-root install)
hooks.json                   Antigravity Stop hook registration
skills/tts/SKILL.md          Antigravity skill → cli.py
hosts/cursor/                Cursor hooks + install.sh + /tts command + skill
hosts/antigravity/           Antigravity scaffold + run/install shims
docs/multi-host.md           Multi-host decisions and status
scripts/run, scripts/run.cmd   Cross-platform Python launcher (finds python3/python/py)
scripts/tts_reader/
  adapters/                  Host Stop-payload → SpeakRequest mappers
  sanitize.py                Markdown to utterance queue
  transcript.py              Final-message polling + multi-host discovery
  cursor_install.py          Merge-safe Cursor hooks + /tts command/skill writer

  engine/                    Pluggable speech backends + factory
    base.py                    Backend interface
    macos.py                   macOS `say`
    windows.py                 Windows SAPI via PowerShell
    linux.py                   Linux espeak-ng / spd-say
    cloud.py                   ElevenLabs / OpenAI / Azure
    player.py                  Cross-platform audio-file player (cloud)
  daemon.py                  Queue, channels, and session arbitration
  client.py                  Daemon startup and loopback-TCP client
  hook.py                    Claude Stop-hook entry point
  hook_cursor.py             Cursor stop-hook entry point
  hook_antigravity.py        Antigravity Stop-hook entry point
  hook_common.py             Shared Stop-hook runner
  cli.py                     /tts command dispatcher
  config.py                  Configuration and data paths
tests/                       Unit tests (no audio required)
```

## Limitations

- Playback depends on a working speech engine for your platform (`say` on
  macOS, SAPI/PowerShell on Windows, `espeak-ng`/`spd-say` on Linux) or, for
  the cloud backend, network access and a valid API key.
- Voice availability and quality depend on the platform, its version, language,
  and downloaded voice assets. On macOS, Siri voices cannot be selected by name.
- The cloud backend synthesizes over the network, so its first-audio latency is
  higher than the local engines and it incurs provider usage costs.
- Transcript readers cover Claude Code JSONL, Cursor role-nested JSONL, and
  Antigravity step logs; those formats are not stable public interfaces and may
  change. Failures stay silent rather than blocking a turn.
- `/tts replay` and `/tts preview` prefer the last Stop-hook transcript
  (`last_speak.json`), then host-specific locators for the current working
  directory. Multiple sessions in the same directory can still make selection
  ambiguous.
- If the final transcript message is delayed by more than three seconds, the
  daemon gives up on that job silently rather than speaking anything.
- All sessions sharing the data directory share one configuration and one
  playback queue. There are no per-session voices, rates, or enable switches.
- `/tts stop` and `/tts off` interrupt the active job but do not empty the
  pending queue, so responses queued before the command can still play.
- Automatic hook jobs use Claude Code's session ID, while `/tts replay` uses the
  current working directory as its session key. This can make replay identity
  and announcements less precise when several sessions share a directory.
- Session announcements use only the working directory's basename, so projects
  with the same final directory name sound identical.
- Code blocks and tables are intentionally summarized rather than read.
- The sanitizer handles common Markdown and identifier patterns, not every
  possible Markdown extension or pronunciation.
- Speech errors are deliberately swallowed so a TTS failure never blocks a
  Claude Code turn. Check `daemon.log` when playback silently fails.
