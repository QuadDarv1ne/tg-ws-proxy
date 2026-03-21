"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path_safe():
    """
    Safe tmp_path fixture for Windows.

    Uses tempfile module to avoid pytest-asyncio conflicts on Windows.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)
