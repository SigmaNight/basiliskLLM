"""Dialog windows for managing conversation profiles in the BasiliskLLM application."""

from logging import getLogger
from typing import Optional

import wx

from basilisk.config import ConversationProfile, conversation_profiles

from .base_conversation import BaseConversation

log = getLogger(__name__)


class EditConversationProfileDialog(wx.Dialog, BaseConversation):
	"""Dialog for creating or editing a conversation profile."""

	def __init__(
		self,
		parent: wx.Window,
		title: str,
		size: tuple[int, int] = (400, 400),
		profile: ConversationProfile | None = None,
	):
		"""Initialize the dialog for creating or editing a conversation profile.

		Args:
			parent: The parent window for the dialog.
			title: The title of the dialog window.
			size: The size of the dialog window.
			profile: The profile to edit or None to create a new profile.
		"""
		wx.Dialog.__init__(self, parent=parent, title=title, size=size)
		BaseConversation.__init__(self)
		self.profile = profile
		self.init_ui()
		self.apply_profile(self.profile, True)
		self.adjust_advanced_mode_setting()

	def init_ui(self):
		"""Initialize the user interface elements of the dialog."""
		self.sizer = wx.BoxSizer(wx.VERTICAL)

		label = wx.StaticText(
			self,
			# translators: Label for the name of a conversation profile
			label=_("profile &name:"),
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
			label=_("&Include account in profile"),
		)
		self.sizer.Add(self.include_account_checkbox, 0, wx.ALL, 5)
		label = self.create_system_prompt_widget()
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.sizer.Add(self.system_prompt_txt, 0, wx.ALL | wx.EXPAND, 5)
		label = self.create_model_widget()
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.sizer.Add(self.model_list, 0, wx.ALL | wx.EXPAND, 5)
		self.create_max_tokens_widget()
		self.sizer.Add(self.max_tokens_spin_label, 0, wx.ALL, 5)
		self.sizer.Add(self.max_tokens_spin_ctrl, 0, wx.ALL | wx.EXPAND, 5)
		self.create_temperature_widget()
		self.sizer.Add(self.temperature_spinner_label, 0, wx.ALL, 5)
		self.sizer.Add(self.temperature_spinner, 0, wx.ALL | wx.EXPAND, 5)
		self.create_top_p_widget()
		self.sizer.Add(self.top_p_spinner_label, 0, wx.ALL, 5)
		self.sizer.Add(self.top_p_spinner, 0, wx.ALL | wx.EXPAND, 5)
		self.create_stream_widget()
		self.sizer.Add(self.stream_mode, 0, wx.ALL | wx.EXPAND, 5)
		self.ok_button = wx.Button(self, wx.ID_OK)
		self.cancel_button = wx.Button(self, wx.ID_CANCEL)
		self.Bind(wx.EVT_BUTTON, self.on_ok, self.ok_button)
		self.Bind(wx.EVT_BUTTON, self.on_cancel, self.cancel_button)
		self.SetDefaultItem(self.ok_button)
		self.sizer.Add(self.ok_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)
		self.sizer.Add(self.cancel_button, 0, wx.ALL | wx.ALIGN_CENTER, 5)
		self.SetSizerAndFit(self.sizer)

	def apply_profile(
		self,
		profile: ConversationProfile | None,
		fall_back_default_account: bool = False,
	):
		"""Apply the settings from a conversation profile to the dialog controls.

		Args:
			profile: The profile to apply settings from.
			fall_back_default_account: Whether to use the default account if none is specified.
		"""
		super().apply_profile(profile, fall_back_default_account)
		if not profile:
			return None
		self.profile_name_txt.SetValue(profile.name)
		if profile.account or profile.ai_model_info:
			self.include_account_checkbox.SetValue(profile.account is not None)

	def on_ok(self, event: wx.Event | None):
		"""Handle the OK button click by saving the profile settings.

		Validates the profile settings and creates or updates the conversation profile
		with the current dialog values.
		"""
		if not self.profile:
			self.profile = ConversationProfile.model_construct()
		self.profile.name = self.profile_name_txt.GetValue()
		if not self.profile.name:
			wx.MessageBox(
				# translators: Message box title for a conversation profile name
				_("Profile name cannot be empty"),
				# translators: Message box title for a conversation profile name
				_("Profile name error"),
				style=wx.OK | wx.ICON_ERROR,
			)
			return
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
		if model and max_tokens > 0:
			self.profile.max_tokens = max_tokens
		else:
			self.profile.max_tokens = None
		temperature = self.temperature_spinner.GetValue()
		if model and temperature != model.default_temperature:
			self.profile.temperature = temperature
		else:
			self.profile.temperature = None
		top_p = self.top_p_spinner.GetValue()
		if model and top_p != 1.0:
			self.profile.top_p = top_p
		else:
			self.profile.top_p = None
		self.profile.stream_mode = self.stream_mode.GetValue()
		ConversationProfile.model_validate(self.profile)
		self.EndModal(wx.ID_OK)

	def on_cancel(self, event: wx.Event | None):
		"""Handle the Cancel button click by closing the dialog without saving."""
		self.EndModal(wx.ID_CANCEL)


class ConversationProfileDialog(wx.Dialog):
	"""Dialog for managing conversation profiles."""

	def __init__(
		self, parent: wx.Window, title: str, size: tuple[int, int] = (400, 400)
	):
		"""Initialize the dialog for managing conversation profiles.

		Args:
			parent: The parent window for the dialog.
			title: The title of the dialog window.
			size: The size of the dialog window.
		"""
		super().__init__(parent, title=title, size=size)
		self.profiles = conversation_profiles()
		self.menu_update = False
		self.init_ui()
		self.init_data()

	def init_ui(self):
		"""Initialize the user interface elements of the dialog."""
		self.panel = wx.Panel(self)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		label = wx.StaticText(
			self.panel,
			# translators: Label for the conversation profile dialog
			label=_("Conversation &Profiles"),
		)
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.list_profile_ctrl = wx.ListCtrl(self.panel, style=wx.LC_REPORT)
		self.list_profile_ctrl.InsertColumn(
			0,
			# translators: Column header for the name of a conversation profile
			_("Profile name"),
			width=140,
		)
		self.sizer.Add(self.list_profile_ctrl, 1, wx.ALL | wx.EXPAND, 5)
		self.list_profile_ctrl.Bind(
			wx.EVT_KEY_DOWN, self.on_list_profile_key_down
		)
		self.list_profile_ctrl.Bind(
			wx.EVT_LIST_ITEM_SELECTED, self.on_list_item_selected
		)
		self.profile_detail_label = wx.StaticText(
			self.panel, label=_("Profile de&tails:")
		)
		self.sizer.Add(self.profile_detail_label, 0, wx.ALL, 5)
		self.profile_detail_label.Disable()
		self.profile_detail_text = wx.TextCtrl(
			self.panel, style=wx.TE_MULTILINE | wx.TE_READONLY
		)
		self.sizer.Add(self.profile_detail_text, 1, wx.ALL | wx.EXPAND, 5)
		self.profile_detail_text.Disable()
		self.add_btn = wx.Button(
			self.panel,
			# translators: Button label to add a new conversation profile
			label=_("&Add"),
		)

		self.edit_btn = wx.Button(
			self.panel,
			# translators: Button label to edit a conversation profile
			label=_("&Edit"),
		)
		self.edit_btn.Disable()
		self.remove_btn = wx.Button(
			self.panel,
			# translators: Button label to remove a conversation profile
			label=_("&Remove"),
		)
		self.remove_btn.Disable()
		self.default_btn = wx.ToggleButton(
			self.panel,
			# translators: Button label to set a conversation profile as the default
			label=_("&Default Profile"),
		)
		self.default_btn.Disable()
		self.close_button = wx.Button(self.panel, id=wx.ID_CLOSE)
		self.SetDefaultItem(self.close_button)
		self.btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.btn_sizer.Add(self.add_btn, 0, wx.ALL, 5)
		self.btn_sizer.Add(self.edit_btn, 0, wx.ALL, 5)
		self.btn_sizer.Add(self.remove_btn, 0, wx.ALL, 5)
		self.btn_sizer.Add(self.default_btn, 0, wx.ALL, 5)
		self.btn_sizer.Add(self.close_button, 0, wx.ALL, 5)

		self.sizer.Add(self.btn_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 5)
		self.panel.SetSizerAndFit(self.sizer)

		self.add_btn.Bind(wx.EVT_BUTTON, self.on_add)
		self.edit_btn.Bind(wx.EVT_BUTTON, self.on_edit)
		self.remove_btn.Bind(wx.EVT_BUTTON, self.on_remove)
		self.default_btn.Bind(wx.EVT_TOGGLEBUTTON, self.on_default)
		self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
		self.SetEscapeId(self.close_button.GetId())

	def init_data(self):
		"""Initialize the dialog data and update the UI."""
		self.update_ui()

	@property
	def current_profile_index(self) -> Optional[int]:
		"""Get the index of the currently selected profile.

		Returns:
			The index of the selected profile or None if no profile is selected.
		"""
		index = self.list_profile_ctrl.GetFirstSelected()
		return index if index != wx.NOT_FOUND else None

	@property
	def current_profile(self) -> Optional[ConversationProfile]:
		"""Get the currently selected conversation profile.

		Returns:
			The selected profile or None if no profile is selected.
		"""
		return (
			self.profiles[self.current_profile_index]
			if self.current_profile_index is not None
			else None
		)

	def update_ui(self):
		"""Update the user interface to reflect the current profiles list."""
		self.list_profile_ctrl.DeleteAllItems()
		for profile_name in map(lambda x: x.name, self.profiles):
			self.list_profile_ctrl.Append([profile_name])

	def on_add(self, event: wx.Event | None):
		"""Handle adding a new conversation profile.

		Args:
			event: The event that triggered the add action.
		"""
		dialog = EditConversationProfileDialog(
			self,
			# translators: Dialog title to add a new conversation profile
			title=_("Add Conversation Profile"),
		)
		if dialog.ShowModal() == wx.ID_OK:
			self.profiles.add(dialog.profile)
			self.update_ui()
			self.profiles.save()
			self.on_list_item_selected(None)
			self.menu_update = True
		dialog.Destroy()

	def on_edit(self, event: wx.Event | None):
		"""Handle editing the selected conversation profile.

		Args:
			event: The event that triggered the edit action.
		"""
		profile_index = self.current_profile_index
		if profile_index is None:
			return
		dialog = EditConversationProfileDialog(
			self,
			"Edit Conversation Profile",
			profile=self.profiles[profile_index],
		)
		if dialog.ShowModal() == wx.ID_OK:
			self.profiles[profile_index] = dialog.profile
			self.profiles.save()
			self.update_ui()
			self.list_profile_ctrl.SetItemState(
				profile_index,
				wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
				wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			)
			self.on_list_item_selected(None)
			self.menu_update = True
		dialog.Destroy()

	def update_profile_detail(self, profile: ConversationProfile):
		"""Update the profile details text area with the selected profile's information.

		Args:
			profile: The profile whose details should be displayed.
		"""
		self.profile_detail_text.SetValue(self.build_profile_summary(profile))

	def on_remove(self, event: wx.Event | None):
		"""Handle removing the selected conversation profile.

		Args:
			event: The event that triggered the remove action.
		"""
		profile = self.current_profile
		if profile is None:
			return
		confirm_msg = wx.MessageBox(
			# translators: Message box title for removing a conversation profile
			_("Are you sure you want to remove the profile: %s?")
			% profile.name,
			# translators: Message box title for removing a conversation profile
			_("Remove Profile %s") % profile.name,
			style=wx.YES_NO | wx.ICON_QUESTION,
		)
		if confirm_msg == wx.YES:
			self.profiles.remove(profile)
			self.profiles.save()
			self.update_ui()
			self.on_list_item_selected(None)
			self.menu_update = True

	def on_default(self, event: wx.Event | None):
		"""Handle setting the selected profile as the default profile.

		Args:
			event: The event that triggered the default action.
		"""
		profile = self.current_profile
		if profile is None:
			return
		self.profiles.set_default_profile(profile)
		self.profiles.save()

	def build_profile_summary(self, profile: ConversationProfile) -> str:
		"""Build a human-readable summary of a conversation profile.

		Args:
			profile: The profile to summarize.

		Returns:
			A formatted string containing the profile's settings.
		"""
		if profile is None:
			return ""
		# translators: Summary of a conversation profile
		summary = _("Name:") + f" {profile.name}\n"
		if profile.account:
			# translators: Summary of a conversation profile
			summary += _("Account name:") + f" {profile.account.name}\n"
		if profile.ai_model_info:
			# translators: Summary of a conversation profile
			summary += _("Model:") + f" {profile.ai_model_info}\n"
		if profile.max_tokens:
			# translators: Summary of a conversation profile
			summary += _("Max output tokens:") + f" {profile.max_tokens}\n"
		if profile.temperature:
			# translators: Summary of a conversation profile
			summary += _("Temperature:") + f" {profile.temperature}\n"
		if profile.top_p:
			# translators: Summary of a conversation profile
			summary += _("Top P:") + f" {profile.top_p}\n"
		# translators: Summary of a conversation profile
		stream_mode_value = _("yes") if profile.stream_mode else _("no")
		# translators: Summary of a conversation profile
		summary += _("Stream mode:") + f" {stream_mode_value}\n"
		if profile.system_prompt:
			# translators: Summary of a conversation profile
			summary += _("System prompt:") + f"\n{profile.system_prompt}"
		return summary

	def on_list_item_selected(self, event: wx.Event | None):
		"""Handle selection changes in the profiles list.

		Args:
			event: The event that triggered the selection change.
		"""
		profile = self.current_profile
		enable = profile is not None
		self.profile_detail_label.Enable(enable)
		self.profile_detail_text.Enable(enable)
		self.update_profile_detail(profile)
		self.default_btn.Enable(enable)
		self.edit_btn.Enable(enable)
		self.remove_btn.Enable(enable)
		self.default_btn.SetValue(profile == self.profiles.default_profile)

	def on_close(self, event: wx.Event | None):
		"""Handle the dialog close event.

		Args:
			event: The event that triggered the close action.
		"""
		self.EndModal(wx.ID_CLOSE)

	def on_list_profile_key_down(self, event: wx.KeyEvent):
		"""Handle keyboard events in the profiles list.

		Supports Delete for removing profiles and Enter for editing profiles.

		Args:
			event: The key event that triggered the action.
		"""
		if event.GetKeyCode() == wx.WXK_DELETE:
			self.on_remove(event)
		elif event.GetKeyCode() == wx.WXK_RETURN:
			self.on_edit(event)
		event.Skip()
