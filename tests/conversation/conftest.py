"""Shared fixtures for conversation tests."""

import pytest
from upath import UPath


@pytest.fixture
def bskc_path(tmp_path):
	"""Return a test BSKC file path."""
	return tmp_path / "test_conversation.bskc"


@pytest.fixture
def storage_path():
	"""Return an in-memory storage path for conversation restore tests."""
	return UPath("memory://test")
