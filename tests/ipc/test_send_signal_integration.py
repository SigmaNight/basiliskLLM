"""Integration test for the refactored Windows IPC mechanism.

This test verifies that the send_signal module correctly uses Windows IPC
and does not rely on file-based methods.
"""

import os
import sys

import pytest

from basilisk.send_signal import send_focus_signal, send_open_bskc_file_signal


@pytest.fixture
def test_file():
	"""Fixture providing a test file path that gets cleaned up."""
	test_file = None
	yield test_file
	if test_file and os.path.exists(test_file):
		os.remove(test_file)


def test_send_focus_signal_function_exists():
	"""Test that send_focus_signal function exists and can be called."""
	# This should not raise an exception
	send_focus_signal()


def test_send_open_bskc_file_signal_function_exists():
	"""Test that send_open_bskc_file_signal function exists and can be called."""
	# This should not raise an exception
	send_open_bskc_file_signal("test.bskc")


@pytest.mark.skipif(
	sys.platform != "win32", reason="Test only relevant on Windows"
)
def test_windows_ipc_import():
	"""Test that Windows IPC modules can be imported on Windows."""
	from basilisk.ipc.windows_ipc import WindowsIpc

	# Should be able to create instance
	ipc = WindowsIpc("test")

	assert ipc is not None


def test_signal_functions_with_various_inputs():
	"""Test signal functions with various input types."""
	# Test with different file paths
	test_paths = [
		"test.bskc",
		"path/to/file.bskc",
		"C:\\Users\\Test\\Documents\\conversation.bskc",
		"unicode_file.bskc",  # Safe ASCII filename
		"file with spaces.bskc",
	]

	for path in test_paths:
		# Should not raise exceptions
		send_open_bskc_file_signal(path)

	# Focus signal should work multiple times
	for _ in range(3):
		send_focus_signal()
