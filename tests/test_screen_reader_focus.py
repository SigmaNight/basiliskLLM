"""Test script for screen reader focus improvements.

This script tests the focus behavior improvements for screen readers like NVDA.
"""

import builtins
import sys
import unittest
from unittest.mock import MagicMock, patch


# Define the translation function for tests
def _(origin_str: str) -> str:
	"""Mock translation function for tests."""
	return origin_str


# Make the translation function available globally
builtins._ = _

# Only run on Windows since this is Windows-specific functionality
if sys.platform == "win32":
	import wx

	class TestScreenReaderFocus(unittest.TestCase):
		"""Test cases for screen reader focus improvements."""

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

		@patch('win32gui.SetFocus')
		@patch('win32gui.SetForegroundWindow')
		@patch('win32gui.SetActiveWindow')
		@patch('win32gui.ShowWindow')
		@patch('win32gui.BringWindowToTop')
		def test_force_focus_for_screen_reader_with_mocked_win32(
			self,
			mock_bring_window_to_top,
			mock_show_window,
			mock_set_active_window,
			mock_set_foreground_window,
			mock_set_focus,
		):
			"""Test the force_focus_for_screen_reader method with mocked Windows APIs."""
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Import after wx.App is created
			from basilisk.gui.main_frame import MainFrame

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
			mock_set_active_window.assert_not_called()
			mock_set_foreground_window.assert_not_called()

		def test_force_focus_fallback_without_win32(self):
			"""Test that the method works without pywin32 available."""
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Import after wx.App is created
			from basilisk.gui.main_frame import MainFrame

			# Create a test frame
			frame = MainFrame(None, title="Test Frame", conf=MagicMock())

			# Mock the GetHandle method to return a fake handle
			frame.GetHandle = MagicMock(return_value=12345)

			# Patch sys.platform to simulate non-Windows environment
			with patch('sys.platform', 'linux'):
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

			# Mock the current_tab property to return None
			with patch.object(
				type(frame),
				'current_tab',
				new_callable=lambda: property(lambda self: None),
			):
				# This should not raise an exception
				frame._focus_on_conversation_input()

		@patch('win32gui.SetFocus')
		@patch('win32gui.SetForegroundWindow')
		@patch('win32gui.SetActiveWindow')
		@patch('win32gui.ShowWindow')
		@patch('win32gui.BringWindowToTop')
		def test_force_focus_fallback_chain(
			self,
			mock_bring_window_to_top,
			mock_show_window,
			mock_set_active_window,
			mock_set_foreground_window,
			mock_set_focus,
		):
			"""Test that the method tries fallback methods when BringWindowToTop fails."""
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Import after wx.App is created
			from basilisk.gui.main_frame import MainFrame

			# Create a test frame
			frame = MainFrame(None, title="Test Frame", conf=MagicMock())

			# Mock the GetHandle method to return a fake handle
			frame.GetHandle = MagicMock(return_value=12345)

			# Configure BringWindowToTop to return False (failure)
			mock_bring_window_to_top.return_value = False
			# Configure ShowWindow and SetActiveWindow to return True (success)
			mock_show_window.return_value = True
			mock_set_active_window.return_value = True

			# Call the method
			frame.force_focus_for_screen_reader()

			# Verify that all methods were called in the correct order
			mock_bring_window_to_top.assert_called_once_with(12345)
			mock_show_window.assert_called_once()
			mock_set_active_window.assert_called_once()
			# SetForegroundWindow should not be called since ShowWindow/SetActiveWindow succeeded
			mock_set_foreground_window.assert_not_called()

		@patch('win32gui.SetFocus')
		@patch('win32gui.SetForegroundWindow')
		@patch('win32gui.SetActiveWindow')
		@patch('win32gui.ShowWindow')
		@patch('win32gui.BringWindowToTop')
		def test_force_focus_all_methods_fail(
			self,
			mock_bring_window_to_top,
			mock_show_window,
			mock_set_active_window,
			mock_set_foreground_window,
			mock_set_focus,
		):
			"""Test that all fallback methods are tried when each one fails."""
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Import after wx.App is created
			from basilisk.gui.main_frame import MainFrame

			# Create a test frame
			frame = MainFrame(None, title="Test Frame", conf=MagicMock())

			# Mock the GetHandle method to return a fake handle
			frame.GetHandle = MagicMock(return_value=12345)

			# Configure all methods to return False (failure)
			mock_bring_window_to_top.return_value = False
			mock_show_window.return_value = False
			mock_set_active_window.return_value = False
			mock_set_foreground_window.return_value = False

			# Call the method
			frame.force_focus_for_screen_reader()

			# Verify that all methods were called
			mock_bring_window_to_top.assert_called_once_with(12345)
			mock_show_window.assert_called_once()
			mock_set_active_window.assert_called_once()
			mock_set_foreground_window.assert_called_once_with(12345)

		def test_focus_on_conversation_input_with_valid_tab(self):
			"""Test _focus_on_conversation_input with a valid tab and prompt panel."""
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Import after wx.App is created
			from basilisk.gui.main_frame import MainFrame

			# Create a test frame
			frame = MainFrame(None, title="Test Frame", conf=MagicMock())

			# Mock the current_tab and its components
			mock_tab = MagicMock()
			mock_prompt_panel = MagicMock()
			mock_prompt = MagicMock()

			mock_tab.prompt_panel = mock_prompt_panel
			mock_prompt_panel.prompt = mock_prompt

			# Mock _notify_windows_focus_change to avoid Windows API calls
			frame._notify_windows_focus_change = MagicMock()

			with patch.object(
				type(frame),
				'current_tab',
				new_callable=lambda: property(lambda self: mock_tab),
			):
				# Call the method
				frame._focus_on_conversation_input()

				# Verify that SetFocus was called on the prompt
				mock_prompt.SetFocus.assert_called_once()
				# Verify that _notify_windows_focus_change was called on Windows
				if sys.platform == "win32":
					frame._notify_windows_focus_change.assert_called_once_with(
						mock_prompt
					)

		def test_focus_on_conversation_input_no_prompt_panel(self):
			"""Test _focus_on_conversation_input when tab has no prompt_panel."""
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Import after wx.App is created
			from basilisk.gui.main_frame import MainFrame

			# Create a test frame
			frame = MainFrame(None, title="Test Frame", conf=MagicMock())

			# Mock the current_tab with no prompt_panel
			mock_tab = MagicMock()
			mock_tab.prompt_panel = None

			with patch.object(
				type(frame),
				'current_tab',
				new_callable=lambda: property(lambda self: mock_tab),
			):
				# This should not raise an exception
				frame._focus_on_conversation_input()

		@patch('win32gui.SetFocus')
		def test_notify_windows_focus_change_success(self, mock_set_focus):
			"""Test _notify_windows_focus_change when SetFocus succeeds."""
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Import after wx.App is created
			from basilisk.gui.main_frame import MainFrame

			# Create a test frame
			frame = MainFrame(None, title="Test Frame", conf=MagicMock())

			# Mock a control with a handle
			mock_ctrl = MagicMock()
			mock_ctrl.GetHandle.return_value = 54321
			mock_set_focus.return_value = True

			# Call the method
			frame._notify_windows_focus_change(mock_ctrl)

			# Verify SetFocus was called with the correct handle
			mock_set_focus.assert_called_once_with(54321)

		@patch('win32gui.SetFocus')
		def test_notify_windows_focus_change_failure(self, mock_set_focus):
			"""Test _notify_windows_focus_change when SetFocus fails."""
			# Create a minimal wx app for testing
			self.app = wx.App()

			# Import after wx.App is created
			from basilisk.gui.main_frame import MainFrame

			# Create a test frame
			frame = MainFrame(None, title="Test Frame", conf=MagicMock())

			# Mock a control with a handle
			mock_ctrl = MagicMock()
			mock_ctrl.GetHandle.return_value = 54321
			mock_set_focus.return_value = False

			# Call the method (should not raise an exception)
			frame._notify_windows_focus_change(mock_ctrl)

			# Verify SetFocus was called with the correct handle
			mock_set_focus.assert_called_once_with(54321)

else:
	# Create a dummy test class for non-Windows platforms
	class TestScreenReaderFocus(unittest.TestCase):
		"""Dummy test class for non-Windows platforms."""

		def test_skip_on_non_windows(self):
			"""Skip test on non-Windows platforms."""
			self.skipTest("Screen reader focus tests only apply to Windows")


if __name__ == "__main__":
	unittest.main()
