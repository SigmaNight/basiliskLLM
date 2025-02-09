"""Module for the ReadOnlyMessageDialog class."""

import wx


class ReadOnlyMessageDialog(wx.Dialog):
	"""Dialog for displaying a read-only message."""

	def __init__(self, parent: wx.Window, title: str, message: str):
		"""Initialize the dialog.

		Args:
			parent: The parent window.
			title: The dialog title.
			message: The message to display.
		"""
		super().__init__(parent, title=title, size=(800, 600))

		vbox = wx.BoxSizer(wx.VERTICAL)

		text_ctrl = wx.TextCtrl(
			self,
			value=message,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_NONE,
		)
		text_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

		vbox.Add(text_ctrl, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

		close_button = wx.Button(self, id=wx.ID_CLOSE)
		close_button.Bind(wx.EVT_BUTTON, lambda _: self.Close())
		close_button.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

		vbox.Add(
			close_button, proportion=0, flag=wx.ALIGN_CENTER | wx.ALL, border=10
		)

		self.SetSizer(vbox)

	def on_key_down(self, event):
		"""Close the dialog on escape key press.

		Args:
			event: The key down event.
		"""
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self.Close()
		else:
			event.Skip()
