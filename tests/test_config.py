"""Tests for config load/save and the data-dir layout."""

from tts_reader import config

# Captured at import time, before the autouse `isolated_data_dir` fixture
# monkeypatches `config.data_dir` per-test, so tests that need the real
# implementation can call this directly.
_real_data_dir = config.data_dir


def test_defaults_when_no_file():
    cfg = config.load_config()
    assert cfg["enabled"] is False
    assert cfg["mode"] == "summary"
    assert cfg["wpm"] == 175
    assert cfg["header_voice"] is None


def test_set_values_persists():
    config.set_values(enabled=True, wpm=200)
    cfg = config.load_config()
    assert cfg["enabled"] is True
    assert cfg["wpm"] == 200
    # untouched keys keep defaults
    assert cfg["mode"] == "summary"


def test_set_values_ignores_none():
    config.set_values(prose_voice="Alex")
    config.set_values(prose_voice=None)  # should not clobber
    assert config.load_config()["prose_voice"] == "Alex"


def test_corrupt_config_falls_back(isolated_data_dir):
    config.config_path().write_text("{ not valid json")
    cfg = config.load_config()
    assert cfg == config.DEFAULT_CONFIG


def test_paths_live_in_data_dir(isolated_data_dir):
    for p in (config.config_path(), config.port_path(),
              config.pid_path(), config.log_path()):
        assert str(p).startswith(str(isolated_data_dir))


def test_data_dir_uses_canonical_when_fresh(monkeypatch, tmp_path):
    """Fresh install: neither dir exists → create/use ~/.agent-tts."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.delenv(config.DATA_DIR_ENV, raising=False)
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "hook-scoped-dir"))

    resolved = _real_data_dir()

    assert resolved == fake_home / ".agent-tts"
    assert resolved.is_dir()


def test_data_dir_keeps_legacy_when_canonical_missing(monkeypatch, tmp_path):
    """If only ~/.claude/claude-code-tts exists, keep using it (no copy)."""
    fake_home = tmp_path / "home"
    legacy = fake_home / ".claude" / "claude-code-tts"
    legacy.mkdir(parents=True)
    (legacy / "config.json").write_text('{"enabled": true}\n')
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.delenv(config.DATA_DIR_ENV, raising=False)

    resolved = _real_data_dir()

    assert resolved == legacy
    assert not (fake_home / ".agent-tts").exists()


def test_data_dir_prefers_canonical_when_both_exist(monkeypatch, tmp_path):
    fake_home = tmp_path / "home"
    canonical = fake_home / ".agent-tts"
    legacy = fake_home / ".claude" / "claude-code-tts"
    canonical.mkdir(parents=True)
    legacy.mkdir(parents=True)
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.delenv(config.DATA_DIR_ENV, raising=False)

    assert _real_data_dir() == canonical


def test_data_dir_env_override(monkeypatch, tmp_path):
    override = tmp_path / "custom-tts"
    fake_home = tmp_path / "home"
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.setenv(config.DATA_DIR_ENV, str(override))

    resolved = _real_data_dir()

    assert resolved == override
    assert override.is_dir()


def test_data_dir_ignores_claude_plugin_data_env(monkeypatch, tmp_path):
    """Regression: $CLAUDE_PLUGIN_DATA must not split hook vs CLI state."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.delenv(config.DATA_DIR_ENV, raising=False)
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "hook-scoped-dir"))

    resolved = _real_data_dir()

    assert resolved == fake_home / ".agent-tts"
    assert resolved != tmp_path / "hook-scoped-dir"


def test_cli_and_hook_contexts_agree_on_config(monkeypatch, tmp_path):
    """End-to-end regression: cli.py and hook.py share one resolved data dir."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.setattr(config, "data_dir", _real_data_dir)
    monkeypatch.delenv(config.DATA_DIR_ENV, raising=False)

    # cli.py's execution context: Claude Code does not set this for inline bash.
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    config.set_values(enabled=True)  # what `/tts on` does

    # hook.py's execution context: Claude Code scopes hook subprocesses to a
    # per-plugin data dir via this env var.
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "plugins/data/claude-code-tts-tailrace"))
    cfg = config.load_config()  # what hook.py reads to decide whether to speak

    assert cfg["enabled"] is True
    assert config.config_path().parent == fake_home / ".agent-tts"


def test_consume_command_suppression_false_when_not_marked():
    assert config.consume_command_suppression() is False


def test_consume_command_suppression_is_single_use():
    config.mark_command_run()
    assert config.consume_command_suppression() is True
    assert config.consume_command_suppression() is False


def test_consume_command_suppression_ignores_stale_marker():
    config.suppress_marker_path().write_text("0")  # epoch 0: ancient
    assert config.consume_command_suppression(max_age=60.0) is False
