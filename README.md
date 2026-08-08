# claude-code-tts

A macOS plugin that reads Claude Code's completed responses aloud. It cleans up
Markdown before speaking, can use different voices for prose and headings, and
coordinates playback across multiple Claude Code sessions so they do not talk
over one another.

The plugin is opt-in and uses only Python's standard library plus the macOS
`say` command. Nothing is sent to an external text-to-speech service.

## Prerequisites

- macOS with working audio output and the built-in `say` command
- Claude Code with plugin support
- Python 3.9 or newer (`python3 --version`)
- Git, if installing from a source checkout

Quickly verify the local speech engine before installing:

```bash
command -v python3
command -v say
say "Text to speech is working"
```

## Install

This repository is currently a standalone plugin, not a Claude Code marketplace.
Clone it, then load the checkout directly:

```bash
git clone <repository-url> ~/src/claude-code-tts
claude --plugin-dir ~/src/claude-code-tts
```

`--plugin-dir` loads the plugin for that Claude Code process. Use an absolute
path if the shell expands `~` differently in your setup. To load it every time,
add a shell function to `~/.zshrc`:

```bash
claude() {
  command claude --plugin-dir "$HOME/src/claude-code-tts" "$@"
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
| `/tts replay` | Replay the latest response for the current working directory |
| `/tts stop` | Stop current playback and clear the queue |
| `/tts preview` | Print exactly what would be spoken, including voice assignments, without playing audio |
| `/tts voice prose <name>` | Select the voice used for normal prose |
| `/tts voice header <name>` | Select a second voice for headings and blockquotes |
| `/tts wpm <number>` | Set the speaking rate in words per minute |
| `/tts voices` | List voices that the macOS `say` command can select |
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
  "wpm": 175
}
```

Use the `/tts` commands rather than editing this file where possible. A `null`
prose voice tells `say` to use the macOS system voice. A `null` header voice
uses the prose voice, which disables the audible prose/header distinction.
There is not currently a reset-voice command; set either value back to `null`
in `config.json` when you need to return to these defaults.

Configuration and daemon state are stored under:

```text
$CLAUDE_PLUGIN_DATA/
  config.json
  daemon.log
  daemon.pid
  daemon.sock
```

When `CLAUDE_PLUGIN_DATA` is not set, the fallback is
`~/.claude/claude-code-tts`. The daemon exits after 30 minutes without queued or
active work and starts again automatically when needed.

## Voice quality

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

## How it works

Claude Code runs the plugin's `Stop` hook after a turn. The transcript may not
yet contain the final assistant message at that instant, so the hook only sends
a small job to a background player daemon. The daemon polls the transcript for
up to three seconds, extracts the newest assistant text, converts it into an
utterance queue, and invokes `say` once per utterance.

This delay avoids reading the previous answer or an early “let me check that”
message written before tool calls complete.

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
cd ~/src/claude-code-tts
git pull --ff-only
```

Start a new Claude Code process afterward. During plugin development,
`/reload-plugins` can reload plugin components. The player daemon is detached
from Claude Code, however, so restarting Claude Code does not replace an already
running daemon. It exits automatically after 30 idle minutes. To apply daemon
code changes immediately, stop it after playback has finished:

```bash
data_dir="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/claude-code-tts}"
test ! -f "$data_dir/daemon.pid" || kill "$(cat "$data_dir/daemon.pid")"
```

The next response starts the updated daemon automatically.

## Uninstall

1. Run `/tts off` to stop playback and disable the plugin.
2. Remove `--plugin-dir ~/src/claude-code-tts` from your Claude Code command or
   remove the shell function shown above.
3. Close Claude Code sessions that loaded the plugin.
4. Stop the detached daemon so previously queued responses cannot continue:

   ```bash
   data_dir="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/claude-code-tts}"
   test ! -f "$data_dir/daemon.pid" || kill "$(cat "$data_dir/daemon.pid")"
   ```

5. Delete the source checkout:

   ```bash
   rm -rf ~/src/claude-code-tts
   ```

6. Optionally remove saved settings and logs:

   ```bash
   rm -rf "$data_dir"
   ```

If Claude Code supplied a custom `CLAUDE_PLUGIN_DATA` directory, remove that
plugin data directory instead of the fallback path.

## Development

Clone the repository, create a virtual environment, and install the test
dependency:

```bash
cd ~/src/claude-code-tts
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
`$CLAUDE_PLUGIN_DATA/daemon.log` or the fallback data directory.

Project layout:

```text
.claude-plugin/plugin.json   Plugin manifest
hooks/hooks.json             Stop hook registration
commands/tts.md              /tts slash command
scripts/tts_reader/
  sanitize.py                Markdown to utterance queue
  transcript.py              Final assistant-message polling
  engine.py                  macOS `say` wrapper
  daemon.py                  Queue, channels, and session arbitration
  client.py                  Daemon startup and socket client
  hook.py                    Stop-hook entry point
  cli.py                     /tts command dispatcher
  config.py                  Configuration and data paths
tests/                       Unit tests (no audio required)
```

## Limitations

- macOS only; playback depends on the platform-specific `say` command.
- Voice availability and quality depend on the macOS version, language, and
  downloaded voice assets. Siri voices cannot be selected by name.
- The plugin reads Claude Code's internal JSONL transcript format, which is not
  a stable public interface and may change in a future Claude Code release.
- The transcript lookup used by `/tts replay` and `/tts preview` selects the
  newest transcript for the current working directory. Multiple sessions in
  the same directory can make that selection ambiguous.
- If the final transcript message is delayed by more than three seconds, the
  daemon falls back to the newest assistant text it can find, which may be stale.
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
