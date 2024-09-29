from logging import getLogger
from typing import Optional

import wx

from basilisk.config import ConversationProfile, conversation_profiles

from .base_conversation import BaseConversation

log = getLogger(__name__)


class EditConversationProfileDialog(wx.Dialog, BaseConversation):
	def __init__(
		self,
		parent,
		title: str,
		size=(400, 400),
		profile: Optional[ConversationProfile] = None,
	):
		super().__init__(parent, title=title, size=size)
		self.profile = profile
		BaseConversation.__init__(self)
		self.init_ui()
		self.init_data()

	def init_ui(self):
		self.sizer = wx.BoxSizer(wx.VERTICAL)

		label = wx.StaticText(
			self,
			# translators: Label for the name of a conversation profile
			label=_("profile name:"),
		)
		self.sizer.Add(label, 0, wx.ALL, 5)

		self.profile_name_txt = wx.TextCtrl(self)
		self.sizer.Add(self.profile_name_txt, 0, wx.ALL | wx.EXPAND, 5)

		label = self.create_account_widget()
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.sizer.Add(self.account_combo, 0, wx.ALL | wx.EXPAND, 5)
		self.include_account_checkbox = wx.CheckBox(
			self,
			# translators: Label for including an account in a conversation profile
			label=_("Include account in profile"),
		)
		label = self.create_system_prompt_widget()
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.sizer.Add(self.system_prompt_txt, 0, wx.ALL | wx.EXPAND, 5)
		label = self.create_model_widget()
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.sizer.Add(self.model_list, 0, wx.ALL | wx.EXPAND, 5)
		label = self.create_max_tokens_widget()
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.sizer.Add(self.max_tokens_spin_ctrl, 0, wx.ALL | wx.EXPAND, 5)
		label = self.create_temperature_widget()
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.sizer.Add(self.temperature_spinner, 0, wx.ALL | wx.EXPAND, 5)
		label = self.create_top_p_widget()
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.sizer.Add(self.top_p_spinner, 0, wx.ALL | wx.EXPAND, 5)
		self.create_stream_widget()
		self.sizer.Add(self.stream_mode, 0, wx.ALL | wx.EXPAND, 5)
		self.ok_button = wx.Button(self, wx.ID_OK, label="OK")
		self.cancel_button = wx.Button(self, wx.ID_CANCEL, label="Cancel")
		self.sizer.Add(self.ok_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)
		self.sizer.Add(self.cancel_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)

		self.SetSizerAndFit(self.sizer)
		self.Bind(wx.EVT_BUTTON, self.on_ok, self.ok_button)
		self.Bind(wx.EVT_BUTTON, self.on_cancel, self.cancel_button)

	def init_data(self):
		if self.profile:
			self.profile_name_txt.SetValue(self.profile.name)
			self.system_prompt_txt.SetValue(self.profile.system_prompt)
			if self.profile.account or self.profile.ai_model_info:
				self.include_account_checkbox.SetValue(
					self.profile.account is not None
				)
				self.set_account_and_model_from_profile(self.profile)
				if self.profile.max_tokens:
					self.max_tokens_spin_ctrl.SetValue(self.profile.max_tokens)
				if self.profile.temperature:
					self.temperature_spinner.SetValue(self.profile.temperature)
				if self.profile.top_p:
					self.top_p_spinner.SetValue(self.profile.top_p)
				self.stream_mode.SetValue(self.profile.stream_mode)
				return
		else:
			self.select_default_account()

	def on_ok(self, event):
		if not self.profile:
			self.profile = ConversationProfile.model_construct()
		self.profile.name = self.profile_name_txt.GetValue()
		self.profile.system_prompt = self.system_prompt_txt.GetValue()
		account = self.current_account
		model = self.current_model
		if self.include_account_checkbox.GetValue():
			self.profile.set_account(account)
		else:
			self.profile.set_account(None)
		if account and model:
			self.profile.set_model_info(
				self.current_account.provider.id, self.current_model.id
			)
		else:
			self.profile.ai_model_info = None
		max_tokens = self.max_tokens_spin_ctrl.GetValue()
		if max_tokens > 0:
			self.profile.max_tokens = max_tokens
		else:
			self.profile.max_tokens = None
		temperature = self.temperature_spinner.GetValue()
		if temperature != model.default_temperature:
			self.profile.temperature = temperature
		else:
			self.profile.temperature = None
		top_p = self.top_p_spinner.GetValue()
		if top_p != 1.0:
			self.profile.top_p = top_p
		else:
			self.profile.top_p = None
		self.profile.stream_mode = self.stream_mode.GetValue()
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

		self.list_profile_ctrl = wx.ListCtrl(self.panel, style=wx.LC_REPORT)
		self.list_profile_ctrl.InsertColumn(
			0,
			# translators: Column header for the name of a conversation profile
			_("Profile name"),
			width=140,
		)
		self.list_profile_ctrl.InsertColumn(1, "System Prompt", width=240)
		self.sizer.Add(self.list_profile_ctrl, 1, wx.ALL | wx.EXPAND, 5)
		self.list_profile_ctrl.Bind(
			wx.EVT_KEY_DOWN, self.on_list_profile_key_down
		)
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
		self.close_button = wx.Button(self.panel, id=wx.ID_CLOSE)

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
			self.list_profile_ctrl,
		)
		self.Bind(wx.EVT_BUTTON, self.on_close, self.close_button)

	def init_data(self):
		self.update_ui()

	def update_ui(self):
		self.list_profile_ctrl.DeleteAllItems()
		for i, profile in enumerate(self.profiles):
			self.list_profile_ctrl.InsertItem(index=i, label=profile.name)
			self.list_profile_ctrl.SetItem(i, 1, profile.system_prompt)

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
		index = self.list_profile_ctrl.GetFirstSelected()
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
		index = self.list_profile_ctrl.GetFirstSelected()
		if index != wx.NOT_FOUND:
			del self.profiles[index]
			self.profiles.save()
			self.update_ui()

	def on_default(self, event):
		index = self.list_profile_ctrl.GetFirstSelected()
		if index != wx.NOT_FOUND:
			self.profiles.default_profile_name = self.profiles[index].name

	def on_list_item_selected(self, event):
		index = self.list_profile_ctrl.GetFirstSelected()
		if index != wx.NOT_FOUND:
			profile = self.profiles[index]
			self.default_button.SetValue(
				profile == self.profiles.default_profile
			)
			self.default_button.Enable()
			self.edit_button.Enable()
			self.remove_button.Enable()
		else:
			self.default_button.Disable()
			self.edit_button.Disable()
			self.remove_button.Disable()

	def on_close(self, event):
		self.EndModal(wx.ID_CLOSE)

	def on_list_profile_key_down(self, event: wx.KeyEvent):
		if event.GetKeyCode() == wx.WXK_DELETE:
			self.on_remove(event)
		elif event.GetKeyCode() == wx.WXK_RETURN:
			self.on_edit(event)
		event.Skip()
