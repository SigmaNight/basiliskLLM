"""Enhanced error dialog that can detect URLs and offer to open them in browser.

This module provides an enhanced error dialog that replaces the standard wx.MessageBox
for error messages. It can detect URLs in error messages and provide an option to
open them in the system browser.
"""

from __future__ import annotations

from typing import Optional

import wx

from basilisk.presenters.enhanced_error_presenter import EnhancedErrorPresenter


def show_enhanced_error_dialog(
	parent: Optional[wx.Window],
	message: str,
	title: Optional[str] = None,
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

	urls = EnhancedErrorPresenter.find_urls_in_text(message)

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
		self.presenter = EnhancedErrorPresenter(self)

		self._create_ui()
		self._bind_events()
		self.CenterOnParent()
		# Focus OK button when dialog is shown
		self.Bind(wx.EVT_SHOW, self._on_show)

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
		# Translators: Button to copy the error message to the clipboard
		copy_label = _("Copy Error")
		self.copy_btn = wx.Button(self, label=copy_label)
		self._copy_btn_original_label = copy_label
		button_sizer.Add(self.copy_btn, 0, wx.ALL, 5)

		# Spacer to push OK button to the right
		button_sizer.AddStretchSpacer()

		# OK button (right side)
		self.ok_btn = wx.Button(self, wx.ID_OK, _("OK"))
		self.ok_btn.SetDefault()
		button_sizer.Add(self.ok_btn, 0, wx.ALL, 5)

		main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

		self.SetSizer(main_sizer)
		self.Fit()

		# Set minimum size
		min_size = self.GetSize()
		min_size.width = max(min_size.width, 450)
		self.SetMinSize(min_size)

	def _bind_events(self):
		"""Bind event handlers."""
		if hasattr(self, "open_url_btn"):
			self.Bind(wx.EVT_BUTTON, self.on_open_url, self.open_url_btn)
		self.Bind(wx.EVT_BUTTON, self.on_copy_error, self.copy_btn)

	def _on_show(self, event: wx.ShowEvent):
		"""Handle dialog show event to focus OK button.

		Args:
			event: The show event
		"""
		if event.IsShown() and hasattr(self, "ok_btn"):
			self.ok_btn.SetFocus()
		event.Skip()

	def set_copy_state(self, label: str, enabled: bool) -> None:
		"""Update the copy button label and enabled state.

		When disabled, schedules a reset to the original label after 2 seconds.

		Args:
			label: The button label to display.
			enabled: Whether the button should be enabled.
		"""
		self.copy_btn.SetLabel(label)
		if enabled:
			self.copy_btn.Enable()
		else:
			self.copy_btn.Disable()
			wx.CallLater(2000, self._reset_copy_button)

	def _reset_copy_button(self):
		"""Restore the copy button to its original label and enabled state."""
		if self.copy_btn and not self.copy_btn.IsBeingDeleted():
			self.copy_btn.SetLabel(self._copy_btn_original_label)
			self.copy_btn.Enable()

	def set_open_url_state(self, label: str) -> None:
		"""Temporarily update the open-URL button label.

		Schedules a reset to the original label after 2 seconds.

		Args:
			label: The temporary button label to display.
		"""
		if hasattr(self, "open_url_btn"):
			orig = self.open_url_btn.GetLabel()
			self.open_url_btn.SetLabel(label)
			wx.CallLater(2000, self.open_url_btn.SetLabel, orig)

	def bell(self) -> None:
		"""Ring the system bell."""
		wx.Bell()

	def on_copy_error(self, event: wx.CommandEvent):
		"""Handle copying error message to clipboard.

		Args:
			event: Button click event
		"""
		self.presenter.copy_to_clipboard(self.message)

	def on_open_url(self, event: wx.CommandEvent):
		"""Handle opening URL in browser.

		Args:
			event: Button click event
		"""
		if not hasattr(self, "url_choice"):
			return

		selection = self.url_choice.GetSelection()
		if selection == wx.NOT_FOUND or selection >= len(self.urls):
			return

		url = self.urls[selection]
		self.presenter.open_url(url)
