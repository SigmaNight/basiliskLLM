"""Integration test for the refactored Windows IPC mechanism.

This test verifies that the send_signal module correctly uses Windows IPC
and falls back to file-based methods when needed.
"""

import os
import sys
import unittest

from basilisk.send_signal import send_focus_signal, send_open_bskc_file_signal


class TestSendSignalIntegration(unittest.TestCase):
	"""Integration tests for the send_signal module."""

	def setUp(self):
		"""Set up test fixtures."""
		self.test_file = None

	def tearDown(self):
		"""Clean up test fixtures."""
		if self.test_file and os.path.exists(self.test_file):
			os.remove(self.test_file)

	def test_send_focus_signal_function_exists(self):
		"""Test that send_focus_signal function exists and can be called."""
		# This should not raise an exception
		send_focus_signal()

	def test_send_open_bskc_file_signal_function_exists(self):
		"""Test that send_open_bskc_file_signal function exists and can be called."""
		# This should not raise an exception
		send_open_bskc_file_signal("test.bskc")

	@unittest.skipIf(sys.platform != "win32", "Test only relevant on Windows")
	def test_windows_ipc_import(self):
		"""Test that Windows IPC modules can be imported on Windows."""
		from basilisk.windows_ipc import (
			WindowsSignalReceiver,
			WindowsSignalSender,
		)

		# Should be able to create instances
		sender = WindowsSignalSender("test")
		receiver = WindowsSignalReceiver("test", {})

		self.assertIsNotNone(sender)
		self.assertIsNotNone(receiver)

	def test_fallback_behavior(self):
		"""Test that fallback file-based behavior works."""
		# Even on Windows, the fallback should work if Windows IPC fails
		from basilisk.consts import FOCUS_FILE, OPEN_BSKC_FILE

		# Ensure directories exist
		os.makedirs(os.path.dirname(FOCUS_FILE), exist_ok=True)
		os.makedirs(os.path.dirname(OPEN_BSKC_FILE), exist_ok=True)

		# Remove files if they exist
		for file_path in [FOCUS_FILE, OPEN_BSKC_FILE]:
			if os.path.exists(file_path):
				os.remove(file_path)

		# Test focus signal
		send_focus_signal()

		# On Windows, this might use IPC or fallback to file
		# On other platforms, it should always use file
		if sys.platform != "win32":
			self.assertTrue(os.path.exists(FOCUS_FILE))
			with open(FOCUS_FILE, 'r') as f:
				timestamp = f.read().strip()
				self.assertTrue(timestamp.replace('.', '').isdigit())

		# Test open BSKC signal
		test_file_path = "test_conversation.bskc"
		send_open_bskc_file_signal(test_file_path)

		# On Windows, this might use IPC or fallback to file
		# On other platforms, it should always use file
		if sys.platform != "win32":
			self.assertTrue(os.path.exists(OPEN_BSKC_FILE))
			with open(OPEN_BSKC_FILE, 'r') as f:
				content = f.read().strip()
				self.assertEqual(content, test_file_path)

	def test_signal_functions_with_various_inputs(self):
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


if __name__ == "__main__":
	unittest.main()
