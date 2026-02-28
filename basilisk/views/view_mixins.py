"""Reusable view mixins for BasiliskLLM GUI components.

Provides:
- ``ErrorDisplayMixin``: unified error display for wx-based views.
"""

from __future__ import annotations

import wx

from basilisk.views.enhanced_error_dialog import show_enhanced_error_dialog


class ErrorDisplayMixin:
	"""Mixin for views that need standardised error display.

	Provides ``show_error()`` for simple modal error boxes and
	``show_enhanced_error()`` for the richer dialog that detects
	URLs and offers clipboard copy.

	Views can override ``show_error()`` to route simple errors through
	the enhanced dialog (e.g. ``OCRHandler`` does this).
	"""

	def show_error(self, message: str, title: str = None) -> None:
		"""Display a simple error dialog (wx.MessageBox).

		Args:
			message: The error message to display.
			title: Dialog title.  Defaults to the localised "Error" string.
		"""
		if title is None:
			title = _("Error")
		wx.MessageBox(message, title, wx.OK | wx.ICON_ERROR)

	def show_enhanced_error(
		self, message: str, title: str = None, is_completion_error: bool = False
	) -> None:
		"""Display the enhanced error dialog (with URL detection).

		Args:
			message: The error message to display.
			title: Dialog title.  Defaults to the localised "Error" string.
			is_completion_error: When True, adapts explanatory text for
				LLM completion errors.
		"""
		show_enhanced_error_dialog(self, message, title, is_completion_error)
