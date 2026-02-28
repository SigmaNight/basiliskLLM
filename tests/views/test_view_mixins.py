"""Tests for view_mixins.ErrorDisplayMixin."""

from unittest.mock import MagicMock, patch

import pytest


class TestErrorDisplayMixin:
	"""Tests for ErrorDisplayMixin without a real wx application."""

	@pytest.fixture
	def mixin_instance(self):
		"""Return a bare ErrorDisplayMixin instance with wx patched.

		Returns:
			An instance of ErrorDisplayMixin.
		"""
		import sys

		wx_mock = MagicMock()
		wx_mock.OK = 4
		wx_mock.ICON_ERROR = 0x00000040
		wx_mock.NOT_FOUND = -1
		sys.modules.setdefault("wx", wx_mock)

		from basilisk.views.view_mixins import ErrorDisplayMixin

		return ErrorDisplayMixin()

	def test_show_error_calls_messagebox(self, mixin_instance):
		"""show_error should delegate to wx.MessageBox."""
		with patch("basilisk.views.view_mixins.wx") as mock_wx:
			mock_wx.OK = 4
			mock_wx.ICON_ERROR = 0x00000040
			mixin_instance.show_error("oops", "Err")
			mock_wx.MessageBox.assert_called_once_with(
				"oops", "Err", mock_wx.OK | mock_wx.ICON_ERROR
			)

	def test_show_error_default_title(self, mixin_instance):
		"""show_error with no title should use the localised 'Error' string."""
		with patch("basilisk.views.view_mixins.wx") as mock_wx:
			mock_wx.OK = 4
			mock_wx.ICON_ERROR = 0x00000040
			mixin_instance.show_error("oops")
			call_args = mock_wx.MessageBox.call_args.args
			assert call_args[1] == "Error"

	def test_show_enhanced_error_delegates_to_dialog(self, mixin_instance):
		"""show_enhanced_error should call show_enhanced_error_dialog."""
		target = "basilisk.views.view_mixins.show_enhanced_error_dialog"
		with patch(target) as mock_dialog:
			mixin_instance.show_enhanced_error("msg", "title", True)
			mock_dialog.assert_called_once_with(
				mixin_instance, "msg", "title", True
			)

	def test_show_enhanced_error_default_args(self, mixin_instance):
		"""show_enhanced_error default is_completion_error=False."""
		target = "basilisk.views.view_mixins.show_enhanced_error_dialog"
		with patch(target) as mock_dialog:
			mixin_instance.show_enhanced_error("msg")
			mock_dialog.assert_called_once_with(
				mixin_instance, "msg", None, False
			)
