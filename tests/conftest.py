"""Shared fixtures."""

from pathlib import Path

import pytest
from fakes.unreal import FakeUnreal


@pytest.fixture
def ue() -> FakeUnreal:
    return FakeUnreal()


@pytest.fixture
def saved(tmp_path: Path) -> Path:
    folder = tmp_path / "Saved"
    folder.mkdir()
    return folder
