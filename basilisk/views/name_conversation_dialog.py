"""This module provides a dialog for naming or renaming conversations.

The dialog supports both manual name entry and automatic name generation based on conversation content.
"""

import wx


class NameConversationDialog(wx.Dialog):
	"""A dialog to name a conversation.

	Features:
	- Manual name entry
	- Automatic name generation
	- Support for both initial naming and renaming
	"""

	def __init__(self, parent, title="", auto=False):
		"""Create the dialog.

		Args:
			parent: The parent window.
			title: The initial title.
			auto: If True, the dialog will automatically generate a name.
		"""
		super(NameConversationDialog, self).__init__(
			parent, title=_("Name conversation"), size=(300, 200)
		)

		self.parent = parent
		self.auto = auto
		self.title = title
		self._create_ui()

		if auto:
			self.on_generate(None)

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
		try:
			title = self.parent.current_tab.generate_conversation_title()
			if title:
				title = title.strip().replace("\n", " ")
				self.text_ctrl.SetValue(title)
		except Exception as e:
			wx.MessageBox(
				# Translators: A message box title.
				_("Error"),
				# Translators: An error message.
				_("An error occurred while generating the name: %s") % e,
				style=wx.ICON_ERROR,
			)
		if self.generate_button.HasFocus():
			self.text_ctrl.SetFocus()
