"""Test script for screen reader focus improvements.

This script tests the focus behavior improvements for screen readers like NVDA.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

# Only run on Windows since this is Windows-specific functionality
if sys.platform == "win32":
	import wx

	class TestScreenReaderFocus(unittest.TestCase):
		"""Test cases for screen reader focus improvements."""

		def setUp(self):
			"""Set up test fixtures."""
			self.app = None

		def tearDown(self):
			"""Clean up test fixtures."""
			if self.app:
				self.app.Destroy()

		@patch('win32gui.SetForegroundWindow')
		@patch('win32gui.SetActiveWindow')
		@patch('win32api.keybd_event')
		def test_force_focus_for_screen_reader_with_mocked_win32(
			self,
			mock_keybd_event,
			mock_set_active_window,
			mock_set_foreground_window,
		):
			"""Test the force_focus_for_screen_reader method with mocked Windows APIs."""
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Import after wx.App is created
			from basilisk.gui.main_frame import MainFrame

			# Create a test frame
			frame = MainFrame(None, title="Test Frame", conf=MagicMock())

			# Call the method
			frame.force_focus_for_screen_reader()

			# Verify Windows APIs were called
			mock_set_foreground_window.assert_called_once()
			mock_set_active_window.assert_called_once()

			# Verify keyboard events were sent (Alt+Tab sequence)
			expected_calls = [
				# Alt down
				unittest.mock.call(18, 0, 0, 0),  # VK_MENU = 18
				# Tab down
				unittest.mock.call(9, 0, 0, 0),  # VK_TAB = 9
				# Tab up
				unittest.mock.call(9, 0, 2, 0),  # KEYEVENTF_KEYUP = 2
				# Alt up
				unittest.mock.call(
					18, 0, 2, 0
				),  # VK_MENU = 18, KEYEVENTF_KEYUP = 2
			]
			mock_keybd_event.assert_has_calls(expected_calls)

		def test_force_focus_fallback_without_win32(self):
			"""Test that the method works without pywin32 available."""
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Import after wx.App is created
			from basilisk.gui.main_frame import MainFrame

			# Create a test frame
			frame = MainFrame(None, title="Test Frame", conf=MagicMock())

			# Patch the import to simulate pywin32 not being available
			with patch(
				'builtins.__import__',
				side_effect=ImportError("No module named 'win32api'"),
			):
				# This should not raise an exception
				frame.force_focus_for_screen_reader()

		def test_focus_on_conversation_input_without_current_tab(self):
			"""Test _focus_on_conversation_input when no current tab is available."""
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Import after wx.App is created
			from basilisk.gui.main_frame import MainFrame

			# Create a test frame
			frame = MainFrame(None, title="Test Frame", conf=MagicMock())

			# Ensure there's no current_tab
			if hasattr(frame, 'current_tab'):
				delattr(frame, 'current_tab')

			# This should not raise an exception
			frame._focus_on_conversation_input()

else:
	# Create a dummy test class for non-Windows platforms
	class TestScreenReaderFocus(unittest.TestCase):
		"""Dummy test class for non-Windows platforms."""

		def test_skip_on_non_windows(self):
			"""Skip test on non-Windows platforms."""
			self.skipTest("Screen reader focus tests only apply to Windows")


if __name__ == "__main__":
	unittest.main()
