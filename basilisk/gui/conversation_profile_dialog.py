from logging import getLogger
from typing import Optional

import wx

from basilisk.config import conversation_profiles, ConversationProfile

log = getLogger(__name__)


class EditConversationProfileDialog(wx.Dialog):
	def __init__(
		self,
		parent,
		title: str,
		size=(400, 400),
		profile: Optional[ConversationProfile] = None,
	):
		super().__init__(parent, title=title, size=size)
		self.profile = profile
		self.init_ui()
		self.init_data()

	def init_ui(self):
		self.panel = wx.Panel(self)
		self.sizer = wx.BoxSizer(wx.VERTICAL)

		self.name_label = wx.StaticText(
			self.panel,
			# translators: Label for the name of a conversation profile
			label=_("profile name:"),
		)
		self.name_text = wx.TextCtrl(self.panel)
		self.sizer.Add(self.name_label, 0, wx.ALL, 5)
		self.sizer.Add(self.name_text, 0, wx.ALL | wx.EXPAND, 5)

		self.prompt_label = wx.StaticText(self.panel, label="System Prompt:")
		self.prompt_text = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE)
		self.sizer.Add(self.prompt_label, 0, wx.ALL, 5)
		self.sizer.Add(self.prompt_text, 1, wx.ALL | wx.EXPAND, 5)

		self.ok_button = wx.Button(self.panel, wx.ID_OK, label="OK")
		self.cancel_button = wx.Button(self.panel, wx.ID_CANCEL, label="Cancel")
		self.sizer.Add(self.ok_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)
		self.sizer.Add(self.cancel_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)

		self.panel.SetSizerAndFit(self.sizer)
		self.Bind(wx.EVT_BUTTON, self.on_ok, self.ok_button)
		self.Bind(wx.EVT_BUTTON, self.on_cancel, self.cancel_button)

	def init_data(self):
		if self.profile:
			self.name_text.SetValue(self.profile.name)
			self.prompt_text.SetValue(self.profile.system_prompt)

	def on_ok(self, event):
		if not self.profile:
			self.profile = ConversationProfile.model_construct()
		self.profile.name = self.name_text.GetValue()
		self.profile.system_prompt = self.prompt_text.GetValue()

		self.EndModal(wx.ID_OK)

	def on_cancel(self, event):
		self.EndModal(wx.ID_CANCEL)


class ConversationProfileDialog(wx.Dialog):
	"""Manage conversation profiles"""

	def __init__(self, parent, title, size=(400, 400)):
		super().__init__(parent, title=title, size=size)
		self.profiles = conversation_profiles()
		self.init_ui()
		self.init_data()

	def init_ui(self):
		self.panel = wx.Panel(self)
		self.sizer = wx.BoxSizer(wx.VERTICAL)

		self.list_ctrl = wx.ListCtrl(self.panel, style=wx.LC_REPORT)
		self.list_ctrl.InsertColumn(
			0,
			# translators: Column header for the name of a conversation profile
			_("Profile name"),
			width=140,
		)
		self.list_ctrl.InsertColumn(1, "System Prompt", width=240)
		self.sizer.Add(self.list_ctrl, 1, wx.ALL | wx.EXPAND, 5)

		self.add_button = wx.Button(
			self.panel,
			# translators: Button label to add a new conversation profile
			label=_("Add Profile"),
		)
		self.edit_button = wx.Button(
			self.panel,
			# translators: Button label to edit a conversation profile
			label=_("Edit Profile"),
		)
		self.edit_button.Disable()
		self.remove_button = wx.Button(
			self.panel,
			# translators: Button label to remove a conversation profile
			label=_("Remove Profile"),
		)
		self.remove_button.Disable()
		self.default_button = wx.ToggleButton(
			self.panel,
			# translators: Button label to set a conversation profile as the default
			label=_("Default Profile"),
		)
		self.default_button.Disable()
		self.close_button = wx.Button(
			self.panel, id=wx.ID_CLOSE)

		self.button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.button_sizer.Add(self.add_button, 0, wx.ALL, 5)
		self.button_sizer.Add(self.edit_button, 0, wx.ALL, 5)
		self.button_sizer.Add(self.remove_button, 0, wx.ALL, 5)
		self.button_sizer.Add(self.default_button, 0, wx.ALL, 5)
		self.button_sizer.Add(self.close_button, 0, wx.ALL, 5)

		self.sizer.Add(self.button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 5)
		self.panel.SetSizerAndFit(self.sizer)

		self.Bind(wx.EVT_BUTTON, self.on_add, self.add_button)
		self.Bind(wx.EVT_BUTTON, self.on_edit, self.edit_button)
		self.Bind(wx.EVT_BUTTON, self.on_remove, self.remove_button)
		self.Bind(wx.EVT_TOGGLEBUTTON, self.on_default, self.default_button)
		self.Bind(
			wx.EVT_LIST_ITEM_SELECTED,
			self.on_list_item_selected,
			self.list_ctrl,
		)
		self.Bind(wx.EVT_BUTTON, self.on_close, self.close_button)

	def init_data(self):
		self.update_ui()

	def update_ui(self):
		self.list_ctrl.DeleteAllItems()
		for i, profile in enumerate(self.profiles):
			self.list_ctrl.InsertItem(index=i, label=profile.name)
			self.list_ctrl.SetItem(i, 1, profile.system_prompt)

	def on_add(self, event):
		dialog = EditConversationProfileDialog(
			self,
			# translators: Dialog title to add a new conversation profile
			title=_("Add Conversation Profile"),
		)
		if dialog.ShowModal() == wx.ID_OK:
			self.profiles.add(dialog.profile)
			self.update_ui()
			self.profiles.save()

	def on_edit(self, event):
		index = self.list_ctrl.GetFirstSelected()
		if index != wx.NOT_FOUND:
			profile = self.profiles[index]
			dialog = EditConversationProfileDialog(
				self, "Edit Conversation Profile", profile=profile
			)
			if dialog.ShowModal() == wx.ID_OK:
				self.profiles[index] = dialog.profile
				self.update_ui()
				self.profiles.save()

	def on_remove(self, event):
		index = self.list_ctrl.GetFirstSelected()
		if index != wx.NOT_FOUND:
			del self.profiles[index]
			self.profiles.save()
			self.update_ui()

	def on_default(self, event):
		index = self.list_ctrl.GetFirstSelected()
		if index != wx.NOT_FOUND:
			self.profiles.default_profile_name = (self.profiles[index].name)

	def on_list_item_selected(self, event):
		index = self.list_ctrl.GetFirstSelected()
		if index != wx.NOT_FOUND:
			profile = self.profiles[index]
			self.default_button.SetValue(
				profile == self.profiles.default_profile)
			self.default_button.Enable()
			self.edit_button.Enable()
			self.remove_button.Enable()
		else:
			self.default_button.Disable()
			self.edit_button.Disable()
			self.remove_button.Disable()
			
	def on_close(self, event):
		self.EndModal(wx.ID_CLOSE)

