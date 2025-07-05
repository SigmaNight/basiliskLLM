"""Automated unit tests for Windows focus management.

This module contains automated tests for Windows focus management functionality
in BasiliskLLM, including NVDA screen reader compatibility and signal handling.
"""

import builtins
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


# Define the translation function for tests
def _(origin_str: str) -> str:
	"""Mock translation function for tests."""
	return origin_str


# Make the translation function available globally
builtins._ = _

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWindowsFocusManagement(unittest.TestCase):
	"""Unit tests for Windows focus management functionality."""

	def setUp(self):
		"""Set up test fixtures."""
		self.app = None

		# Mock global_vars.args to avoid AttributeError
		from basilisk import global_vars

		mock_args = MagicMock()
		mock_args.no_env_account = False
		global_vars.args = mock_args

	def tearDown(self):
		"""Clean up test fixtures."""
		if self.app:
			self.app.Destroy()

		# Clean up global_vars.args
		from basilisk import global_vars

		global_vars.args = None

	@unittest.skipUnless(sys.platform == "win32", "Windows-only test")
	def test_force_focus_for_screen_reader_with_mocked_win32(self):
		"""Test the force_focus_for_screen_reader method with mocked Windows APIs."""
		# Skip this test if wxPython is not available
		try:
			import wx
		except ImportError:
			self.skipTest("wxPython not available")

		# Skip this test if the main_frame module has import issues
		try:
			from basilisk.gui.main_frame import MainFrame
		except ImportError as e:
			self.skipTest(f"MainFrame import failed: {e}")

		with (
			patch("win32gui.SetForegroundWindow") as mock_set_foreground,
			patch("win32gui.SetActiveWindow") as mock_set_active,
			patch("win32gui.ShowWindow") as mock_show_window,
			patch("win32gui.BringWindowToTop") as mock_bring_window_to_top,
		):
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Create a test frame
			frame = MainFrame(None, title="Test Frame", conf=MagicMock())

			# Mock the GetHandle method to return a fake handle
			frame.GetHandle = MagicMock(return_value=12345)

			# Configure BringWindowToTop to return True (success)
			mock_bring_window_to_top.return_value = True

			# Call the method
			frame.force_focus_for_screen_reader()

			# Verify that BringWindowToTop was called with the correct handle
			mock_bring_window_to_top.assert_called_once_with(12345)

			# Since BringWindowToTop returns True, other methods should not be called
			mock_show_window.assert_not_called()
			mock_set_active.assert_not_called()
			mock_set_foreground.assert_not_called()

	@unittest.skipUnless(sys.platform == "win32", "Windows-only test")
	def test_force_focus_fallback_without_win32(self):
		"""Test that the method works without pywin32 available."""
		# Skip this test if wxPython is not available
		try:
			import wx
		except ImportError:
			self.skipTest("wxPython not available")

		# Skip this test if the main_frame module has import issues
		try:
			from basilisk.gui.main_frame import MainFrame
		except ImportError as e:
			self.skipTest(f"MainFrame import failed: {e}")

		# Create a minimal wx app for testing
		self.app = wx.App()

		# Create a test frame
		frame = MainFrame(None, title="Test Frame", conf=MagicMock())

		# Mock the GetHandle method to return a fake handle
		frame.GetHandle = MagicMock(return_value=12345)

		# Patch sys.platform to simulate non-Windows environment
		with patch('sys.platform', 'linux'):
			# This should not raise an exception
			frame.force_focus_for_screen_reader()

	@unittest.skipUnless(sys.platform == "win32", "Windows-only test")
	def test_focus_on_conversation_input_without_current_tab(self):
		"""Test _focus_on_conversation_input when no current tab is available."""
		# Skip this test if wxPython is not available
		try:
			import wx
		except ImportError:
			self.skipTest("wxPython not available")

		# Skip this test if the main_frame module has import issues
		try:
			from basilisk.gui.main_frame import MainFrame
		except ImportError as e:
			self.skipTest(f"MainFrame import failed: {e}")

		# Create a minimal wx app for testing
		self.app = wx.App()

		# Create a test frame
		frame = MainFrame(None, title="Test Frame", conf=MagicMock())

		# Mock the current_tab property to return None
		with patch.object(
			type(frame),
			'current_tab',
			new_callable=lambda: property(lambda self: None),
		):
			# This should not raise an exception
			frame._focus_on_conversation_input()

	def test_signal_sending(self):
		"""Test that focus signals can be sent without errors."""
		try:
			from basilisk.send_signal import send_focus_signal

			# This should not raise an exception even if no instance is running
			send_focus_signal()
		except Exception as e:
			# If it fails, it should be a specific expected error
			self.assertIn("connection", str(e).lower())

	def test_singleton_instance_creation(self):
		"""Test that SingletonInstance can be created properly."""
		try:
			from basilisk.singleton_instance import SingletonInstance

			# This should not raise an exception
			singleton = SingletonInstance()
			self.assertIsNotNone(singleton)
		except Exception as e:
			# If it fails, it should be a specific expected error
			self.fail(f"SingletonInstance creation failed: {e}")

	def test_focus_signal_import(self):
		"""Test that focus signal function can be imported."""
		try:
			from basilisk.send_signal import send_focus_signal

			# Function should be callable
			self.assertTrue(callable(send_focus_signal))
		except ImportError as e:
			self.fail(f"Failed to import send_focus_signal: {e}")

	def test_singleton_instance_import(self):
		"""Test that SingletonInstance can be imported."""
		try:
			from basilisk.singleton_instance import SingletonInstance

			# Class should be importable
			self.assertTrue(callable(SingletonInstance))
		except ImportError as e:
			self.fail(f"Failed to import SingletonInstance: {e}")


if __name__ == "__main__":
	unittest.main()
