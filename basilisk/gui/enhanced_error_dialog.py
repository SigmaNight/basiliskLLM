"""Enhanced error dialog that can detect URLs and offer to open them in browser.

This module provides an enhanced error dialog that replaces the standard wx.MessageBox
for error messages. It can detect URLs in error messages and provide an option to
open them in the system browser.
"""

from __future__ import annotations

import logging
import re
import webbrowser
from typing import Optional

import wx

logger = logging.getLogger(__name__)

# URL detection pattern that matches http/https URLs
URL_PATTERN = re.compile(
	r'https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?',
	re.IGNORECASE,
)


def find_urls_in_text(text: str) -> list[str]:
	"""Find all URLs in the given text.

	Args:
		text: The text to search for URLs

	Returns:
		A list of URLs found in the text
	"""
	return URL_PATTERN.findall(text)


def show_enhanced_error_dialog(
	parent: Optional[wx.Window],
	message: str,
	title: str = None,
	is_completion_error: bool = False,
) -> int:
	"""Show an enhanced error dialog that can handle URLs.

	Args:
		parent: Parent window for the dialog
		message: Error message to display
		title: Dialog title (defaults to "Error")
		is_completion_error: Whether this is a completion error (affects message adaptation)

	Returns:
		wx.ID_OK if OK was clicked, wx.ID_CANCEL if cancelled
	"""
	if title is None:
		title = _("Error")

	urls = find_urls_in_text(message)

	dialog = EnhancedErrorDialog(
		parent, message, title, urls, is_completion_error
	)
	result = dialog.ShowModal()
	dialog.Destroy()
	return result


class EnhancedErrorDialog(wx.Dialog):
	"""Enhanced error dialog that can detect URLs and offer to open them."""

	def __init__(
		self,
		parent: Optional[wx.Window],
		message: str,
		title: str,
		urls: list[str],
		is_completion_error: bool = False,
	):
		"""Initialize the enhanced error dialog.

		Args:
			parent: Parent window
			message: Error message to display
			title: Dialog title
			urls: List of URLs found in the message
			is_completion_error: Whether this is a completion error
		"""
		super().__init__(
			parent,
			title=title,
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)

		self.message = message
		self.urls = urls
		self.is_completion_error = is_completion_error

		self._create_ui()
		self._bind_events()
		self.CenterOnParent()

	def _create_ui(self):
		"""Create the dialog UI."""
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		# Icon and message section
		message_sizer = wx.BoxSizer(wx.HORIZONTAL)

		# Error icon
		error_icon = wx.StaticBitmap(self)
		error_icon.SetBitmap(
			wx.ArtProvider.GetBitmap(wx.ART_ERROR, wx.ART_MESSAGE_BOX, (32, 32))
		)
		message_sizer.Add(error_icon, 0, wx.ALL | wx.ALIGN_TOP, 10)

		# Message text
		message_text = wx.StaticText(
			self, label=self.message, style=wx.ST_NO_AUTORESIZE
		)
		message_text.Wrap(400)  # Wrap text at 400 pixels
		message_sizer.Add(message_text, 1, wx.ALL | wx.EXPAND, 10)

		main_sizer.Add(message_sizer, 1, wx.EXPAND)

		# URL section if URLs are present
		if self.urls:
			# Separator
			main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.ALL, 5)

			# URL info text
			if self.is_completion_error:
				url_info_text = _(
					"This completion error contains a URL that might provide more information about the issue:"
				)
			else:
				url_info_text = _(
					"This error message contains a URL that might provide more information:"
				)

			url_info = wx.StaticText(self, label=url_info_text)
			url_info.Wrap(400)
			main_sizer.Add(url_info, 0, wx.ALL | wx.EXPAND, 10)

			# URL list and open button
			url_sizer = wx.BoxSizer(wx.HORIZONTAL)

			# URL choice control
			self.url_choice = wx.Choice(self, choices=self.urls)
			if self.urls:
				self.url_choice.SetSelection(0)
			url_sizer.Add(self.url_choice, 1, wx.ALL | wx.EXPAND, 5)

			# Open URL button
			self.open_url_btn = wx.Button(self, label=_("Open in Browser"))
			url_sizer.Add(self.open_url_btn, 0, wx.ALL, 5)

			main_sizer.Add(url_sizer, 0, wx.EXPAND | wx.ALL, 5)

		# Button sizer
		button_sizer = wx.BoxSizer(wx.HORIZONTAL)

		# Copy button (left side)
		self.copy_btn = wx.Button(self, label=_("Copy Error"))
		button_sizer.Add(self.copy_btn, 0, wx.ALL, 5)

		# Spacer to push OK button to the right
		button_sizer.AddStretchSpacer()

		# OK button (right side)
		ok_btn = wx.Button(self, wx.ID_OK, _("OK"))
		ok_btn.SetDefault()
		button_sizer.Add(ok_btn, 0, wx.ALL, 5)

		main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

		self.SetSizer(main_sizer)
		self.Fit()

		# Set minimum size
		min_size = self.GetSize()
		min_size.width = max(min_size.width, 450)
		self.SetMinSize(min_size)

	def _bind_events(self):
		"""Bind event handlers."""
		if hasattr(self, 'open_url_btn'):
			self.open_url_btn.Bind(wx.EVT_BUTTON, self.on_open_url)
		self.copy_btn.Bind(wx.EVT_BUTTON, self.on_copy_error)

	def on_copy_error(self, event: wx.CommandEvent):
		"""Handle copying error message to clipboard.

		Args:
			event: Button click event
		"""
		try:
			if wx.TheClipboard.Open():
				wx.TheClipboard.SetData(wx.TextDataObject(self.message))
				wx.TheClipboard.Close()

				# Change button label to show confirmation
				original_label = self.copy_btn.GetLabel()
				self.copy_btn.SetLabel(_("Copied!"))
				self.copy_btn.Disable()

				# Reset button label after 2 seconds
				wx.CallLater(2000, self._reset_copy_button, original_label)
			else:
				wx.MessageBox(
					_("Failed to access clipboard"),
					_("Error"),
					wx.OK | wx.ICON_ERROR,
					self,
				)
		except Exception as e:
			logger.error("Failed to copy to clipboard: %s", e)
			wx.MessageBox(
				_("Failed to copy to clipboard: ") + str(e),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
				self,
			)

	def _reset_copy_button(self, original_label: str):
		"""Reset the copy button to its original state.

		Args:
			original_label: The original button label to restore
		"""
		if self.copy_btn and not self.copy_btn.IsBeingDeleted():
			self.copy_btn.SetLabel(original_label)
			self.copy_btn.Enable()

	def on_open_url(self, event: wx.CommandEvent):
		"""Handle opening URL in browser.

		Args:
			event: Button click event
		"""
		if not hasattr(self, 'url_choice'):
			return

		selection = self.url_choice.GetSelection()
		if selection == wx.NOT_FOUND or selection >= len(self.urls):
			return

		url = self.urls[selection]
		try:
			logger.info("Opening URL in browser: %s", url)
			webbrowser.open(url)
		except Exception as e:
			logger.error("Failed to open URL %s: %s", url, e)
			wx.MessageBox(
				_("Failed to open URL in browser: ") + str(e),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
				self,
			)
