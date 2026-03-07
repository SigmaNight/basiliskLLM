"""Dialog windows for managing conversation profiles in the BasiliskLLM application."""

from logging import getLogger
from typing import Optional

import wx

import basilisk.config as config
from basilisk.config import (
	ConversationProfile,
	ConversationProfileType,
	VoiceProfileSettings,
	conversation_profiles,
)
from basilisk.decorators import require_list_selection
from basilisk.presenters.conversation_profile_presenter import (
	ConversationProfilePresenter,
	EditConversationProfilePresenter,
)

from .base_conversation import BaseConversation

log = getLogger(__name__)


class EditConversationProfileDialog(wx.Dialog, BaseConversation):
	"""Dialog for creating or editing a conversation profile."""

	def __init__(
		self,
		parent: wx.Window,
		title: str,
		size: tuple[int, int] = (520, 720),
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
		BaseConversation.__init__(self, account_model_service=None)
		self.presenter = EditConversationProfilePresenter(
			view=self, profile=profile
		)
		self.init_ui()
		self.apply_profile(profile, True)
		self.adjust_advanced_mode_setting()

	@property
	def profile(self) -> ConversationProfile | None:
		"""Get the profile from the presenter."""
		return self.presenter.profile

	@property
	def profile_type(self) -> ConversationProfileType:
		"""Get the selected profile type from the UI."""
		index = self.profile_type_combo.GetSelection()
		if index == wx.NOT_FOUND:
			return ConversationProfileType.TEXT
		return self._profile_type_items[index][0]

	def on_profile_type_change(self, event: wx.Event | None):
		"""Handle profile type changes to show/hide voice settings."""
		self._toggle_voice_settings_visibility(
			self.profile_type == ConversationProfileType.VOICE
		)
		self.Layout()

	def _toggle_voice_settings_visibility(self, show: bool):
		self.voice_group_box.Show(show)
		self.voice_group_box.Enable(show)
		self.voice_group_sizer.ShowItems(show)

	def init_ui(self):
		"""Initialize the user interface elements of the dialog."""
		self.sizer = wx.BoxSizer(wx.VERTICAL)

		label = wx.StaticText(
			self,
			# Translators: Label for the name of a conversation profile
			label=_("profile &name:"),
		)
		self.sizer.Add(label, 0, wx.ALL, 5)

		self.profile_name_txt = wx.TextCtrl(self)
		self.sizer.Add(self.profile_name_txt, 0, wx.ALL | wx.EXPAND, 5)

		self._profile_type_items = list(
			ConversationProfileType.get_labels().items()
		)
		label = wx.StaticText(
			self,
			# Translators: Label for the profile type of a conversation profile
			label=_("Profile &type:"),
		)
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.profile_type_combo = wx.ComboBox(
			self,
			style=wx.CB_READONLY,
			choices=[label for _, label in self._profile_type_items],
		)
		self.profile_type_combo.Bind(
			wx.EVT_COMBOBOX, self.on_profile_type_change
		)
		self.sizer.Add(self.profile_type_combo, 0, wx.ALL | wx.EXPAND, 5)

		label = self.create_account_widget()
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.sizer.Add(self.account_combo, 0, wx.ALL | wx.EXPAND, 5)
		self.include_account_checkbox = wx.CheckBox(
			self,
			# Translators: Label for including an account in a conversation profile
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

		self.voice_group_box = wx.StaticBox(
			self,
			# Translators: Label for voice settings in profile dialog
			label=_("Voice settings"),
		)
		self.voice_group_sizer = wx.StaticBoxSizer(
			self.voice_group_box, wx.VERTICAL
		)
		label = wx.StaticText(
			self.voice_group_box,
			# Translators: Label for voice name setting
			label=_("Voice"),
		)
		self.voice_group_sizer.Add(label, 0, wx.ALL, 5)
		self.voice_name = wx.TextCtrl(self.voice_group_box)
		self.voice_group_sizer.Add(self.voice_name, 0, wx.ALL | wx.EXPAND, 5)
		label = wx.StaticText(
			self.voice_group_box,
			# Translators: Label for transcription model setting
			label=_("Transcription model"),
		)
		self.voice_group_sizer.Add(label, 0, wx.ALL, 5)
		self.voice_transcription_model = wx.TextCtrl(self.voice_group_box)
		self.voice_group_sizer.Add(
			self.voice_transcription_model, 0, wx.ALL | wx.EXPAND, 5
		)
		label = wx.StaticText(
			self.voice_group_box,
			# Translators: Label for transcription language setting
			label=_("Transcription language"),
		)
		self.voice_group_sizer.Add(label, 0, wx.ALL, 5)
		self.voice_transcription_language = wx.TextCtrl(self.voice_group_box)
		self.voice_group_sizer.Add(
			self.voice_transcription_language, 0, wx.ALL | wx.EXPAND, 5
		)
		label = wx.StaticText(
			self.voice_group_box,
			# Translators: Label for transcription prompt setting
			label=_("Transcription prompt"),
		)
		self.voice_group_sizer.Add(label, 0, wx.ALL, 5)
		self.voice_transcription_prompt = wx.TextCtrl(self.voice_group_box)
		self.voice_group_sizer.Add(
			self.voice_transcription_prompt, 0, wx.ALL | wx.EXPAND, 5
		)
		label = wx.StaticText(
			self.voice_group_box,
			# Translators: Label for VAD type setting
			label=_("VAD type"),
		)
		self.voice_group_sizer.Add(label, 0, wx.ALL, 5)
		self.voice_vad_type = wx.ComboBox(
			self.voice_group_box, style=wx.CB_READONLY, choices=["semantic_vad"]
		)
		self.voice_group_sizer.Add(
			self.voice_vad_type, 0, wx.ALL | wx.EXPAND, 5
		)
		label = wx.StaticText(
			self.voice_group_box,
			# Translators: Label for VAD eagerness setting
			label=_("VAD eagerness"),
		)
		self.voice_group_sizer.Add(label, 0, wx.ALL, 5)
		self.voice_vad_eagerness = wx.ComboBox(
			self.voice_group_box,
			style=wx.CB_READONLY,
			choices=["auto", "low", "medium", "high"],
		)
		self.voice_group_sizer.Add(
			self.voice_vad_eagerness, 0, wx.ALL | wx.EXPAND, 5
		)
		self.voice_interrupt_response = wx.CheckBox(
			self.voice_group_box,
			# Translators: Label for interrupt response setting
			label=_("Allow interruption"),
		)
		self.voice_group_sizer.Add(self.voice_interrupt_response, 0, wx.ALL, 5)
		self.voice_create_response = wx.CheckBox(
			self.voice_group_box,
			# Translators: Label for create response setting
			label=_("Auto create responses"),
		)
		self.voice_group_sizer.Add(self.voice_create_response, 0, wx.ALL, 5)
		label = wx.StaticText(
			self.voice_group_box,
			# Translators: Label for voice output speed setting
			label=_("Output speed"),
		)
		self.voice_group_sizer.Add(label, 0, wx.ALL, 5)
		self.voice_output_speed = wx.SpinCtrlDouble(
			self.voice_group_box, min=0.25, max=1.5, inc=0.05
		)
		self.voice_group_sizer.Add(
			self.voice_output_speed, 0, wx.ALL | wx.EXPAND, 5
		)
		self.sizer.Add(self.voice_group_sizer, 0, wx.ALL | wx.EXPAND, 5)
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
			self.profile_type_combo.SetSelection(0)
			self._toggle_voice_settings_visibility(False)
			self._apply_voice_settings(None)
			return None
		self.profile_name_txt.SetValue(profile.name)
		profile_type = profile.profile_type
		profile_type_index = next(
			(
				index
				for index, (ptype, _) in enumerate(self._profile_type_items)
				if ptype == profile_type
			),
			0,
		)
		self.profile_type_combo.SetSelection(profile_type_index)
		self._toggle_voice_settings_visibility(
			profile_type == ConversationProfileType.VOICE
		)
		if profile.account or profile.ai_model_info:
			self.include_account_checkbox.SetValue(profile.account is not None)
		self._apply_voice_settings(profile.voice_settings)

	def on_ok(self, event: wx.Event | None):
		"""Handle the OK button click by delegating to the presenter.

		Validates the profile settings and creates or updates the conversation profile
		with the current dialog values.
		"""
		result = self.presenter.validate_and_build_profile()
		if result is None:
			wx.MessageBox(
				# Translators: Message box title for a conversation profile name
				_("Profile name cannot be empty"),
				# Translators: Message box title for a conversation profile name
				_("Profile name error"),
				style=wx.OK | wx.ICON_ERROR,
			)
			return
		self.EndModal(wx.ID_OK)

	def on_cancel(self, event: wx.Event | None):
		"""Handle the Cancel button click by closing the dialog without saving."""
		self.EndModal(wx.ID_CANCEL)

	def _apply_voice_settings(self, settings: VoiceProfileSettings | None):
		defaults = config.conf().voice
		self.voice_name.SetValue(
			(settings.voice if settings else defaults.voice) or ""
		)
		self.voice_transcription_model.SetValue(
			(
				settings.transcription_model
				if settings
				else defaults.transcription_model
			)
			or ""
		)
		self.voice_transcription_language.SetValue(
			(
				settings.transcription_language
				if settings
				else defaults.transcription_language
			)
			or ""
		)
		self.voice_transcription_prompt.SetValue(
			(
				settings.transcription_prompt
				if settings
				else defaults.transcription_prompt
			)
			or ""
		)
		self.voice_vad_type.SetValue(
			(settings.vad_type if settings else defaults.vad_type)
			or "semantic_vad"
		)
		self.voice_vad_eagerness.SetValue(
			(settings.vad_eagerness if settings else defaults.vad_eagerness)
			or "auto"
		)
		self.voice_interrupt_response.SetValue(
			settings.interrupt_response
			if settings is not None
			else defaults.interrupt_response
		)
		self.voice_create_response.SetValue(
			settings.create_response
			if settings is not None
			else defaults.create_response
		)
		self.voice_output_speed.SetValue(
			float(
				(settings.output_speed if settings else defaults.output_speed)
				or 1.0
			)
		)

	def get_voice_settings(self) -> VoiceProfileSettings:
		"""Read voice widget values and return a VoiceProfileSettings."""
		return VoiceProfileSettings(
			voice=self.voice_name.GetValue().strip() or "marin",
			transcription_model=(
				self.voice_transcription_model.GetValue().strip()
				or "gpt-4o-mini-transcribe"
			),
			transcription_language=(
				self.voice_transcription_language.GetValue().strip() or None
			),
			transcription_prompt=(
				self.voice_transcription_prompt.GetValue().strip() or None
			),
			vad_type=self.voice_vad_type.GetValue() or "semantic_vad",
			vad_eagerness=self.voice_vad_eagerness.GetValue() or "auto",
			interrupt_response=self.voice_interrupt_response.GetValue(),
			create_response=self.voice_create_response.GetValue(),
			output_speed=float(self.voice_output_speed.GetValue()),
		)


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
		profiles = conversation_profiles()
		self.presenter = ConversationProfilePresenter(
			view=self, profiles=profiles
		)
		self.init_ui()
		self.init_data()

	@property
	def profiles(self):
		"""Get the profiles from the presenter."""
		return self.presenter.profiles

	@property
	def menu_update(self) -> bool:
		"""Get the menu_update flag from the presenter."""
		return self.presenter.menu_update

	def init_ui(self):
		"""Initialize the user interface elements of the dialog."""
		self.panel = wx.Panel(self)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		label = wx.StaticText(
			self.panel,
			# Translators: Label for the conversation profile dialog
			label=_("Conversation &Profiles"),
		)
		self.sizer.Add(label, 0, wx.ALL, 5)
		self.list_profile_ctrl = wx.ListCtrl(self.panel, style=wx.LC_REPORT)
		self.list_profile_ctrl.InsertColumn(
			0,
			# Translators: Column header for the name of a conversation profile
			_("Profile name"),
			width=140,
		)
		self.list_profile_ctrl.InsertColumn(
			1,
			# Translators: Column header for the type of a conversation profile
			_("Type"),
			width=80,
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
			# Translators: Button label to add a new conversation profile
			label=_("&Add"),
		)

		self.edit_btn = wx.Button(
			self.panel,
			# Translators: Button label to edit a conversation profile
			label=_("&Edit"),
		)
		self.edit_btn.Disable()
		self.remove_btn = wx.Button(
			self.panel,
			# Translators: Button label to remove a conversation profile
			label=_("&Remove"),
		)
		self.remove_btn.Disable()
		self.default_btn = wx.ToggleButton(
			self.panel,
			# Translators: Button label to set a conversation profile as the default
			label=_("&Default Profile"),
		)
		self.default_btn.Disable()
		self.default_voice_btn = wx.ToggleButton(
			self.panel,
			# Translators: Button label to set a voice conversation profile as the default
			label=_("Default &Voice Profile"),
		)
		self.default_voice_btn.Disable()
		self.close_button = wx.Button(self.panel, id=wx.ID_CLOSE)
		self.SetDefaultItem(self.close_button)
		self.btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.btn_sizer.Add(self.add_btn, 0, wx.ALL, 5)
		self.btn_sizer.Add(self.edit_btn, 0, wx.ALL, 5)
		self.btn_sizer.Add(self.remove_btn, 0, wx.ALL, 5)
		self.btn_sizer.Add(self.default_btn, 0, wx.ALL, 5)
		self.btn_sizer.Add(self.default_voice_btn, 0, wx.ALL, 5)
		self.btn_sizer.Add(self.close_button, 0, wx.ALL, 5)

		self.sizer.Add(self.btn_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 5)
		self.panel.SetSizerAndFit(self.sizer)

		self.add_btn.Bind(wx.EVT_BUTTON, self.on_add)
		self.edit_btn.Bind(wx.EVT_BUTTON, self.on_edit)
		self.remove_btn.Bind(wx.EVT_BUTTON, self.on_remove)
		self.default_btn.Bind(wx.EVT_TOGGLEBUTTON, self.on_default)
		self.default_voice_btn.Bind(wx.EVT_TOGGLEBUTTON, self.on_default_voice)
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
		type_labels = ConversationProfileType.get_labels()
		for profile in self.profiles:
			self.list_profile_ctrl.Append(
				[
					profile.name,
					type_labels.get(profile.profile_type, profile.profile_type),
				]
			)

	def on_add(self, event: wx.Event | None):
		"""Handle adding a new conversation profile.

		Args:
			event: The event that triggered the add action.
		"""
		dialog = EditConversationProfileDialog(
			self,
			# Translators: Dialog title to add a new conversation profile
			title=_("Add Conversation Profile"),
		)
		if dialog.ShowModal() == wx.ID_OK:
			self.presenter.add_profile(dialog.profile)
			self.update_ui()
			self.on_list_item_selected(None)
		dialog.Destroy()

	@require_list_selection("list_profile_ctrl")
	def on_edit(self, event: wx.Event | None):
		"""Handle editing the selected conversation profile.

		Args:
			event: The event that triggered the edit action.
		"""
		profile_index = self.current_profile_index
		dialog = EditConversationProfileDialog(
			self,
			# Translators: dialog title
			_("Edit Conversation Profile"),
			profile=self.profiles[profile_index],
		)
		if dialog.ShowModal() == wx.ID_OK:
			self.presenter.edit_profile(profile_index, dialog.profile)
			self.update_ui()
			self.list_profile_ctrl.SetItemState(
				profile_index,
				wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
				wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			)
			self.on_list_item_selected(None)
		dialog.Destroy()

	def update_profile_detail(self, profile: ConversationProfile):
		"""Update the profile details text area with the selected profile's information.

		Args:
			profile: The profile whose details should be displayed.
		"""
		if profile is None:
			self.profile_detail_text.SetValue("")
		else:
			self.profile_detail_text.SetValue(profile.to_summary_text())

	@require_list_selection("list_profile_ctrl")
	def on_remove(self, event: wx.Event | None):
		"""Handle removing the selected conversation profile.

		Args:
			event: The event that triggered the remove action.
		"""
		profile = self.current_profile
		confirm_msg = wx.MessageBox(
			# Translators: Message box title for removing a conversation profile
			_("Are you sure you want to remove the profile: %s?")
			% profile.name,
			# Translators: Message box title for removing a conversation profile
			_("Remove Profile %s") % profile.name,
			style=wx.YES_NO | wx.ICON_QUESTION,
		)
		if confirm_msg == wx.YES:
			self.presenter.remove_profile(profile)
			self.update_ui()
			self.on_list_item_selected(None)

	@require_list_selection("list_profile_ctrl")
	def on_default(self, event: wx.Event | None):
		"""Handle setting the selected profile as the default profile.

		Args:
			event: The event that triggered the default action.
		"""
		profile = self.current_profile
		self.presenter.set_default(profile)

	@require_list_selection("list_profile_ctrl")
	def on_default_voice(self, event: wx.Event | None):
		"""Handle setting the selected profile as the default voice profile."""
		profile = self.current_profile
		self.presenter.set_default_voice(profile)

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
		self.default_voice_btn.Enable(
			enable and profile.profile_type == ConversationProfileType.VOICE
		)
		self.edit_btn.Enable(enable)
		self.remove_btn.Enable(enable)
		self.default_btn.SetValue(profile == self.profiles.default_profile)
		self.default_voice_btn.SetValue(
			profile == self.profiles.default_voice_profile
		)

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
