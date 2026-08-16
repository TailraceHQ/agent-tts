"""The PATH wrapper must follow its install symlink to the checkout."""

import os
import stat
import subprocess
from pathlib import Path

WRAPPER = Path(__file__).resolve().parents[1] / "scripts" / "tts"


def test_tts_wrapper_follows_symlink(tmp_path, monkeypatch):
    """Regression: ~/.local/bin/tts used to exec ~/.local/bin/run."""
    monkeypatch.setenv("AGENT_TTS_DATA_DIR", str(tmp_path / "data"))
    link = tmp_path / "bin" / "tts"
    link.parent.mkdir()
    link.symlink_to(WRAPPER)
    # Make sure the wrapper is executable even on a fresh checkout.
    os.chmod(WRAPPER, os.stat(WRAPPER).st_mode | stat.S_IXUSR)

    proc = subprocess.run(
        [str(link), "status"],
        capture_output=True,
        text=True,
        env={**os.environ, "AGENT_TTS_DATA_DIR": str(tmp_path / "data")},
    )
    assert proc.returncode == 0, proc.stderr
    assert "backend=" in proc.stdout
    assert "No such file or directory" not in proc.stderr
    assert str(tmp_path / "bin" / "run") not in proc.stderr
