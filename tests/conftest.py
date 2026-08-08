"""Shared test setup: put the package on the path and isolate the data dir.

Every test runs against a throwaway ``CLAUDE_PLUGIN_DATA`` so tests never touch
the user's real config, socket, or daemon.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    yield tmp_path
