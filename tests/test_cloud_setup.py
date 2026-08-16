"""Tests for cloud setup apply + wizard flow (no real TTY)."""

from tts_reader import cli, config
from tts_reader.cloud_setup import (
    CUSTOM,
    NOT_TTY,
    apply_setup,
    env_choices,
    run_wizard,
)
from tts_reader.ui import BACK, EXIT


def test_apply_setup_disables_cloud():
    config.set_values(backend="cloud")
    msg = apply_setup(provider=None)
    assert config.load_config()["backend"] == "auto"
    assert "disabled" in msg.lower()


def test_apply_setup_custom_env_name():
    msg = apply_setup(provider="openai", api_key_env="OPEN_AI_ALLOY_VOICE_KEY")
    cfg = config.load_config()
    assert cfg["backend"] == "cloud"
    assert cfg["cloud"]["provider"] == "openai"
    assert cfg["cloud"]["api_key_env"] == "OPEN_AI_ALLOY_VOICE_KEY"
    assert "OPEN_AI_ALLOY_VOICE_KEY" in msg


def test_apply_setup_azure_stores_region():
    apply_setup(provider="azure", api_key_env="AZURE_SPEECH_KEY", region="eastus")
    cloud = config.load_config()["cloud"]
    assert cloud["provider"] == "azure"
    assert cloud["region"] == "eastus"


def test_env_choices_are_only_default_and_type_custom(monkeypatch):
    monkeypatch.setenv("OPEN_AI_ALLOY_VOICE_KEY", "secret")
    monkeypatch.setenv("MY_OTHER_KEY", "x")
    ids = [row[0] for row in env_choices("openai")]
    assert ids == ["OPENAI_API_KEY", CUSTOM]
    assert "OPEN_AI_ALLOY_VOICE_KEY" not in ids


def test_wizard_custom_typed_env():
    answers = iter(["openai", CUSTOM])

    def fake_select(title, choices, **kwargs):
        return next(answers)

    msg = run_wizard(
        select=fake_select,
        prompt=lambda message: "OPEN_AI_ALLOY_VOICE_KEY",
    )
    assert config.load_config()["cloud"]["api_key_env"] == "OPEN_AI_ALLOY_VOICE_KEY"
    assert "OPEN_AI_ALLOY_VOICE_KEY" in msg


def test_wizard_off_disables():
    config.set_values(backend="cloud")
    msg = run_wizard(select=lambda *a, **k: "off")
    assert config.load_config()["backend"] == "auto"
    assert "disabled" in msg.lower()


def test_wizard_exit_does_not_write():
    config.set_values(backend="macos")
    msg = run_wizard(select=lambda *a, **k: EXIT)
    assert config.load_config()["backend"] == "macos"
    assert "cancelled" in msg.lower()


def test_wizard_back_from_env_then_off():
    answers = iter(["openai", BACK, "off"])

    def fake_select(title, choices, **kwargs):
        return next(answers)

    msg = run_wizard(select=fake_select)
    assert config.load_config()["backend"] == "auto"
    assert "disabled" in msg.lower()


def test_wizard_preselects_type_custom_when_env_is_not_default():
    config.set_cloud_values(api_key_env="MY_TTS_API_KEY")
    seen = []
    answers = iter(["openai", CUSTOM])

    def fake_select(title, choices, **kwargs):
        seen.append((kwargs.get("selected_id"), [c[0] for c in choices]))
        return next(answers)

    run_wizard(select=fake_select, prompt=lambda message: "MY_TTS_API_KEY")
    _provider_sel, env_step = seen
    selected_id, choice_ids = env_step
    assert choice_ids == ["OPENAI_API_KEY", CUSTOM]
    assert selected_id == CUSTOM
    assert config.load_config()["cloud"]["api_key_env"] == "MY_TTS_API_KEY"


def test_wizard_azure_region():
    answers = iter(["azure", "AZURE_SPEECH_KEY", "westus2"])

    def fake_select(title, choices, **kwargs):
        return next(answers)

    run_wizard(select=fake_select)
    cloud = config.load_config()["cloud"]
    assert cloud["provider"] == "azure"
    assert cloud["region"] == "westus2"


def test_setup_without_tty_prints_hint(monkeypatch, capsys):
    monkeypatch.setattr("tts_reader.cloud_setup._is_interactive", lambda: False)
    cli.main(["setup"])
    out = capsys.readouterr().out
    assert "interactive terminal" in out.lower()
    assert "YOUR_API_KEY_VAR" in out
    assert NOT_TTY.splitlines()[0] in out


def test_cloud_with_no_args_is_setup(monkeypatch, capsys):
    monkeypatch.setattr("tts_reader.cloud_setup._is_interactive", lambda: False)
    cli.main(["cloud"])
    assert "interactive terminal" in capsys.readouterr().out.lower()
