"""Tests for config load/save and the data-dir layout."""

from tts_reader import config


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
    for p in (config.config_path(), config.socket_path(),
              config.pid_path(), config.log_path()):
        assert str(p).startswith(str(isolated_data_dir))
