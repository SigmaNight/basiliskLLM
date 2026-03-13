"""Dialog for selecting participants in a new group chat.

Lets the user pick 2–4 ConversationProfile entries to seed a group chat.
"""

from __future__ import annotations

import wx

import basilisk.config as config


class NewGroupChatDialog(wx.Dialog):
	"""Dialog for selecting 2–4 conversation profiles as group chat participants.

	Attributes:
		_profiles: Full list of available ConversationProfile objects.
		_checklist: CheckListBox for profile selection.
	"""

	def __init__(self, parent: wx.Window):
		"""Initialize the dialog.

		Args:
			parent: The parent window.
		"""
		super().__init__(
			parent,
			# Translators: Title of the new group chat dialog
			title=_("New group chat"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._profiles = list(config.conversation_profiles())
		self._build_ui()

	def _build_ui(self):
		"""Build and layout all UI elements."""
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Translators: Label for the profile selection list in the new group chat dialog
		label = wx.StaticText(
			self,
			label=_("Select 2–4 conversation profiles for the group chat:"),
		)
		sizer.Add(label, flag=wx.ALL, border=8)

		profile_names = [p.name for p in self._profiles]
		self._checklist = wx.CheckListBox(self, choices=profile_names)
		# Translators: Accessible label for profile checklist
		self._checklist.SetName(_("Profiles"))
		sizer.Add(
			self._checklist, proportion=1, flag=wx.EXPAND | wx.ALL, border=8
		)

		# Translators: Error label shown when too few or too many profiles are selected
		self._error_label = wx.StaticText(self, label="")
		self._error_label.SetForegroundColour(wx.RED)
		sizer.Add(self._error_label, flag=wx.ALL, border=8)

		btn_sizer = wx.StdDialogButtonSizer()
		self._ok_btn = wx.Button(self, wx.ID_OK)
		self._ok_btn.SetDefault()
		btn_sizer.AddButton(self._ok_btn)
		btn_sizer.AddButton(wx.Button(self, wx.ID_CANCEL))
		btn_sizer.Realize()
		sizer.Add(btn_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=8)

		self.SetSizerAndFit(sizer)
		self.SetMinSize((400, 300))

		self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

	def _on_ok(self, event: wx.CommandEvent):
		"""Validate selection before accepting.

		Args:
			event: The button event.
		"""
		count = sum(
			1
			for i in range(self._checklist.GetCount())
			if self._checklist.IsChecked(i)
		)
		if count < 2:
			self._error_label.SetLabel(
				# Translators: Error when too few profiles selected
				_("Please select at least 2 profiles.")
			)
			self.Layout()
			return
		if count > 4:
			self._error_label.SetLabel(
				# Translators: Error when too many profiles selected
				_("Please select at most 4 profiles.")
			)
			self.Layout()
			return
		self.EndModal(wx.ID_OK)

	def get_selected_profiles(self) -> list[config.ConversationProfile]:
		"""Return the selected ConversationProfile objects in checklist order.

		Returns:
			List of selected ConversationProfile instances.
		"""
		return [
			self._profiles[i]
			for i in range(self._checklist.GetCount())
			if self._checklist.IsChecked(i)
		]
