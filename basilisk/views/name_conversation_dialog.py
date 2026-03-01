"""This module provides a dialog for naming or renaming conversations.

The dialog supports both manual name entry and automatic name generation based on conversation content.
"""

from __future__ import annotations

from typing import Callable, Optional

import wx


class NameConversationDialog(wx.Dialog):
	"""A dialog to name a conversation.

	Features:
	- Manual name entry
	- Automatic name generation via an injected callable
	- Support for both initial naming and renaming
	"""

	def __init__(
		self,
		parent,
		title: str = "",
		generate_fn: Optional[Callable[[], Optional[str]]] = None,
	):
		"""Create the dialog.

		Args:
			parent: The parent window.
			title: The initial title.
			generate_fn: Optional callable that returns a generated title string.
		"""
		super(NameConversationDialog, self).__init__(
			parent, title=_("Name conversation"), size=(300, 200)
		)

		self.generate_fn = generate_fn
		self.title = title
		self._create_ui()

	def _create_ui(self):
		"""Create the user interface."""
		vbox = wx.BoxSizer(wx.VERTICAL)

		label = wx.StaticText(
			self,
			# Translators: A label for a text field where the user can enter a name for a conversation.
			label=_("Enter a name for the conversation:"),
		)
		vbox.Add(label, flag=wx.ALL, border=10)

		self.text_ctrl = wx.TextCtrl(self, value=self.title)
		vbox.Add(
			self.text_ctrl,
			proportion=1,
			flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
			border=10,
		)

		self.generate_button = wx.Button(
			self,
			# Translators: A button to generate a name for a conversation.
			label=_("&Generate"),
		)
		vbox.Add(self.generate_button, flag=wx.ALL, border=10)
		self.generate_button.Bind(wx.EVT_BUTTON, self.on_generate)

		hbox = wx.BoxSizer(wx.HORIZONTAL)

		self.ok_button = wx.Button(self, wx.ID_OK)
		self.ok_button.SetDefault()
		self.cancel_button = wx.Button(self, wx.ID_CANCEL)
		hbox.Add(self.ok_button, flag=wx.RIGHT, border=10)
		hbox.Add(self.cancel_button, flag=wx.RIGHT, border=10)

		vbox.Add(hbox, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

		self.SetSizer(vbox)

	def get_name(self):
		"""Return the entered name."""
		return self.text_ctrl.GetValue()

	def on_generate(self, event: wx.Event | None):
		"""Generate a name for the conversation.

		Args:
			event: The event that triggered the generation.
		"""
		if not self.generate_fn:
			return
		try:
			title = self.generate_fn()
			if title:
				self.text_ctrl.SetValue(title.strip().replace("\n", " "))
		except Exception as e:
			wx.MessageBox(
				# Translators: An error message when generating a conversation name fails.
				_("An error occurred while generating the name: %s") % e,
				# Translators: A message box title.
				_("Error"),
				style=wx.OK | wx.ICON_ERROR,
			)
		if self.generate_button.HasFocus():
			self.text_ctrl.SetFocus()
