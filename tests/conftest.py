"""Shared test setup: put the package on the path and isolate the data dir.

Every test runs against a throwaway data dir (patched directly onto
``config.data_dir``, not via ``$CLAUDE_PLUGIN_DATA`` - production code no
longer reads that env var; see config.py for why) so tests never touch the
user's real config, socket, or daemon.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from tts_reader import config  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    yield tmp_path
