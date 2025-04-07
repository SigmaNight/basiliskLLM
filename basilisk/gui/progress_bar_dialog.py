"""This module contains the ProgressBarDialog class, which is a dialog that displays a progress bar with a cancel button."""

import wx


class ProgressBarDialog(wx.Dialog):
	"""Dialog that displays a progress bar with a cancel button."""

	def __init__(
		self,
		parent: wx.Window,
		title: str,
		message: str,
		cancel_flag,
		max_value: int = 100,
	) -> None:
		"""Initializes the dialog.

		Args:
			parent: The parent window.
			title: The dialog title.
			max_value: The maximum value of the progress bar.
			message: The message to display.
			cancel_flag: The flag to indicate if the operation should be cancelled.
		"""
		super().__init__(
			parent,
			title=title,
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)

		self.cancel_flag = cancel_flag

		self.message = wx.StaticText(self, label=message)
		self.progress_bar = wx.Gauge(self, range=max_value)
		self.cancel_button = wx.Button(self, label="Cancel")
		self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)

		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(self.message, 0, wx.EXPAND | wx.ALL, 10)
		sizer.Add(self.progress_bar, 0, wx.EXPAND | wx.ALL, 10)
		sizer.Add(self.cancel_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

		self.SetSizer(sizer)
		self.Fit()

	def on_cancel(self, event):
		"""Sets the cancellation flag to true."""
		self.cancel_flag.value = True

	def update_progress_bar(self, value: int) -> None:
		"""Updates the progress bar value."""
		self.progress_bar.SetValue(value)
		wx.SafeYield()
		self.Update()

	def update_message(self, message: str) -> None:
		"""Updates the message."""
		self.message.SetLabel(message)
		wx.SafeYield()
		self.Update()
