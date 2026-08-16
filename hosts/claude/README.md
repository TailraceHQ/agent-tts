# Claude Code: install and usage

Config and playback are shared with Cursor and Antigravity under `~/.agent-tts/`.

TTS starts **disabled**. Enable it once after install (`/tts:tts on` or `tts on`).

## Keep it installed between sessions (recommended)

```bash
git clone https://github.com/TailraceHQ/agent-tts.git ~/src/agent-tts
~/src/agent-tts/hosts/claude/install.sh
```

Or by hand:

```bash
claude plugin marketplace add ~/src/agent-tts --scope user
claude plugin install tts@tailrace -s user
```

`install.sh` is idempotent. It:

| Step | Effect |
| --- | --- |
| `claude plugin marketplace add` | Registers this checkout as the `tailrace` marketplace (user scope) |
| `claude plugin install tts@tailrace` | Enables the plugin for every Claude Code session |
| `scripts/install-cli.sh` | Symlinks `tts` onto `PATH` (`~/.local/bin/tts`) |

After `git pull` of plugin changes:

```bash
claude plugin update tts@tailrace
```

## This session only (until you quit)

```bash
claude --plugin-dir ~/src/agent-tts
```

`--plugin-dir` is temporary. The plugin is loaded for that process only and disappears when you quit. Use it to try a checkout or iterate on plugin code. It is not a lasting install.

## Usage

```text
/tts:tts on
/tts:tts status
/tts:tts brief
```

Claude Code namespaces the slash command as `/{plugin}:{command}`, so the command is `/tts:tts`, not `/tts`. Subcommands are the same as the `tts` binary. For `stop` / `skip` / `pause` / `resume`, use the binary — slash commands wait on the model.

## Uninstall

```bash
claude plugin uninstall tts@tailrace
claude plugin marketplace remove tailrace
```

Data dir (shared): `~/.agent-tts/` — only remove if you also want Cursor / Antigravity config cleared.

## See also

- [README.md](../../README.md)
- [Install](https://agent-tts.dev/docs/get-started/install)
