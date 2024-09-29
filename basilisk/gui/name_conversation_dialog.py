import wx


class NameConversationDialog(wx.Dialog):
	def __init__(self, parent, title="", auto=False):
		super(NameConversationDialog, self).__init__(
			parent, title=_("Name conversation"), size=(300, 200)
		)

		self.parent = parent
		self.auto = auto
		self.title = title

		vbox = wx.BoxSizer(wx.VERTICAL)

		label = wx.StaticText(
			self,
			# Translators: A label for a text field where the user can enter a name for a conversation.
			label=_("Enter a name for the conversation:"),
		)
		vbox.Add(label, flag=wx.ALL, border=10)

		self.text_ctrl = wx.TextCtrl(self, value=self.title)
		vbox.Add(self.text_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

		self.generate_button = wx.Button(
			self,
			# Translators: A button to generate a name for a conversation.
			label=_("&Generate"),
		)
		vbox.Add(self.generate_button, flag=wx.ALL, border=10)
		self.generate_button.Bind(wx.EVT_BUTTON, self.on_generate)

		hbox = wx.BoxSizer(wx.HORIZONTAL)

		self.ok_button = wx.Button(self, wx.ID_OK)
		self.cancel_button = wx.Button(self, wx.ID_CANCEL)
		hbox.Add(self.ok_button, flag=wx.RIGHT, border=10)
		hbox.Add(self.cancel_button, flag=wx.RIGHT, border=10)

		vbox.Add(hbox, flag=wx.ALIGN_CENTER | wx.ALL, border=10)
		self.SetSizer(vbox)

		if auto:
			self.on_generate(None)

	def get_name(self):
		return self.text_ctrl.GetValue()

	def on_generate(self, event):
		title = self.parent.current_tab.generate_conversation_title()
		if title:
			title = title.strip().replace('\n', ' ')
			self.text_ctrl.SetValue(title)
		if self.generate_button.HasFocus():
			self.text_ctrl.SetFocus()
