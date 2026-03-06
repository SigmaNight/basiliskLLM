"""Base conversation module providing core conversation UI components and functionality."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import wx
from more_itertools import locate
from wx.lib.agw.floatspin import FloatSpin

import basilisk.config as config
from basilisk.presenters.base_conversation_presenter import (
	BaseConversationPresenter,
	ParameterVisibilityState,
)
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.services.account_model_service import AccountModelService

if TYPE_CHECKING:
	from basilisk.provider_engine.base_engine import BaseEngine

log = logging.getLogger(__name__)


class FloatSpinTextCtrlAccessible(wx.Accessible):
	"""Accessible wrapper for FloatSpin text control to improve screen reader support."""

	def __init__(self, win: wx.Window | None = None, name: str | None = None):
		"""Initialize the FloatSpinTextCtrlAccessible instance.

		Args:
			win: The window to make accessible
			name: The accessible name for the control
		"""
		super().__init__(win)
		self._name = name

	def GetName(self, childId: int) -> tuple[int, str]:
		"""Get the accessible name for the control.

		Args:
			childId: The child ID of the control

		Returns:
			a tuple containing the accessible status and name of the control
		"""
		if self._name:
			return (wx.ACC_OK, self._name)
		return super().GetName(childId)


class BaseConversation:
	"""Base class implementing core conversation functionality and UI components.

	Provides the foundation for managing LLM conversations including:
	- Account selection and management
	- Model selection and configuration
	- System prompt handling
	- Parameter controls (temperature, tokens, etc)
	"""

	def __init__(
		self, account_model_service: AccountModelService | None = None
	):
		"""Initialize the BaseConversation instance.

		Args:
			account_model_service: Service for engine cache and
				account/model resolution. A new instance is created
				if not provided.
		"""
		self.base_conv_presenter = BaseConversationPresenter(
			account_model_service
		)
		self._show_reasoning_blocks_override: bool | None = None

	@property
	def account_model_service(self) -> AccountModelService:
		"""Proxy to base_conv_presenter.account_model_service."""
		return self.base_conv_presenter.account_model_service

	@property
	def current_engine(self) -> Optional[BaseEngine]:
		"""Get the engine instance based on the selected account.

		Returns:
			The engine instance for the selected account or None if no account is selected.
		"""
		account = self.current_account
		if not account:
			return None
		return self.base_conv_presenter.get_engine(account)

	def create_account_widget(self) -> wx.StaticText:
		"""Create and configure the account selection combo box.

		Returns:
			The label widget for the account selector
		"""
		label = wx.StaticText(
			self,
			# Translators: This is a label for account in the main window
			label=_("&Account:"),
		)
		self.account_combo = wx.ComboBox(
			self, style=wx.CB_READONLY, choices=self.get_display_accounts()
		)
		self.account_combo.Bind(wx.EVT_COMBOBOX, self.on_account_change)
		return label

	@property
	def current_account(self) -> Optional[config.Account]:
		"""Get the currently selected account.

		Returns:
			The currently selected account or None if no account is selected.
		"""
		accounts = config.accounts()
		account_index = self.account_combo.GetSelection()
		if account_index == wx.NOT_FOUND:
			return None
		return accounts[account_index]

	def set_account_combo(
		self,
		account: config.Account,
		accounts: config.AccountManager | None = None,
	):
		"""Set the selected account in the account combo box.

		Args:
			account: The account to select
			accounts: Account manager instance to use
		"""
		if accounts is None:
			accounts = config.accounts()
		index = next(locate(accounts, lambda a: a == account), wx.NOT_FOUND)
		if index != wx.NOT_FOUND:
			self.account_combo.SetSelection(index)
			self.on_account_change(None)

	def select_default_account(self):
		"""Select the default account if available."""
		if len(self.account_combo.GetItems()) == 0:
			return
		accounts = config.accounts()
		self.set_account_combo(accounts.default_account, accounts)

	def get_display_accounts(self, force_refresh: bool = False) -> list[str]:
		"""Get list of account display names.

		Args:
			force_refresh: Whether to force refresh organization info

		Returns:
		List of account display names
		"""
		return self.base_conv_presenter.get_display_accounts(force_refresh)

	def on_account_change(
		self, event: wx.Event | None
	) -> Optional[config.Account]:
		"""Handle account selection change events.

		Args:
			event: The event triggering the account change
		"""
		account = self.current_account
		if not account:
			return None
		self.base_conv_presenter.get_engine(account)
		self.update_model_list()
		return account

	def create_system_prompt_widget(self) -> wx.StaticText:
		"""Create and configure the system prompt text control.

		Returns:
			wx.StaticText: The label widget for the system prompt
		"""
		label = wx.StaticText(
			self,
			# Translators: This is a label for system prompt in the main window
			label=_("S&ystem prompt:"),
		)
		self.system_prompt_txt = wx.TextCtrl(
			self,
			size=(800, 100),
			style=wx.TE_MULTILINE | wx.TE_WORDWRAP | wx.HSCROLL,
		)
		return label

	def create_model_widget(self) -> wx.StaticText:
		"""Create and configure the model selection list control.

		Returns:
			wx.StaticText: The label widget for the model list
		"""
		label = wx.StaticText(self, label=_("M&odels:"))
		self.model_list = wx.ListCtrl(self, style=wx.LC_REPORT)
		# Translators: This label appears in the main window's list of models
		self.model_list.InsertColumn(0, _("Name"))
		# Translators: This label appears in the main window's list of models to indicate whether the model supports images
		self.model_list.InsertColumn(1, _("Vision"))
		# Translators: This label appears in the main window's list of models
		self.model_list.InsertColumn(2, _("Context window"))
		# Translators: This label appears in the main window's list of models
		self.model_list.InsertColumn(3, _("Max tokens"))
		self.model_list.SetColumnWidth(0, 200)
		self.model_list.SetColumnWidth(1, 100)
		self.model_list.SetColumnWidth(2, 100)
		self.model_list.SetColumnWidth(3, 100)
		self.model_list.Bind(wx.EVT_KEY_DOWN, self.on_model_key_down)
		self.model_list.Bind(wx.EVT_CONTEXT_MENU, self.on_model_context_menu)
		self.model_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_model_change)
		return label

	def update_model_list(self):
		"""Update the model list with current engine's available models."""
		self.model_list.DeleteAllItems()
		for model in self.get_display_models():
			self.model_list.Append(model)

	def get_display_models(self) -> list[tuple[str, str, str]]:
		"""Get list of models for display.

		Returns:
			List of model display information in a tuple format e.g. (name, vision, context window)
		"""
		return self.base_conv_presenter.get_display_models(self.current_engine)

	def set_model_list(self, model: Optional[ProviderAIModel]):
		"""Set the selected model in the model list.

		Args:
			model: Model to select
		"""
		engine = self.current_engine
		if not engine:
			return
		models = engine.models
		index = wx.NOT_FOUND
		if model:
			index = next(locate(models, lambda m: m == model), wx.NOT_FOUND)
		if index != wx.NOT_FOUND:
			self.model_list.SetItemState(
				index,
				wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
				wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			)
			self.on_model_change(None)

	@property
	def current_model(self) -> Optional[ProviderAIModel]:
		"""Get the currently selected model.

		Returns:
			The currently selected model or None if no model is selected.
		"""
		engine = self.current_engine
		if not engine:
			return None
		model_index = self.model_list.GetFirstSelected()
		if model_index == wx.NOT_FOUND:
			return None
		return engine.models[model_index]

	def on_model_change(self, event: wx.Event | None):
		"""Handle model selection change events.

		Args:
			event: The event triggering the model change
		"""
		model = self.current_model
		if model:
			self.temperature_spinner.SetMax(model.max_temperature)
			self.temperature_spinner.SetValue(model.default_temperature)
			self.max_tokens_spin_ctrl.SetMax(model.effective_max_output_tokens)
			self.max_tokens_spin_ctrl.SetValue(0)
		self.update_parameter_controls_visibility()

	def set_account_and_model_from_profile(
		self,
		profile: config.ConversationProfile,
		fall_back_default_account: bool = False,
	):
		"""Configure account and model selection from a profile.

		Delegates account/model resolution to the AccountModelService,
		then updates the UI widgets accordingly.

		Args:
			profile: Profile containing account or model settings
			fall_back_default_account: Whether to use default account as fallback
		"""
		account, model_id = self.base_conv_presenter.resolve_account_and_model(
			profile, fall_back_default_account
		)
		if account is None and model_id is None and fall_back_default_account:
			self.select_default_account()
			return
		if account:
			self.set_account_combo(account)
		engine = self.current_engine
		if not engine:
			return
		if model_id:
			model = engine.get_model(model_id)
			if model:
				self.set_model_list(model)
		self.update_parameter_controls_visibility()

	def on_model_key_down(self, event: wx.KeyEvent):
		"""Handle key down events for model list control.

		Use Enter key to show model details.

		Args:
			event: The key event triggering the model key down event
		"""
		if event.GetKeyCode() == wx.WXK_RETURN:
			self.on_show_model_details(None)
		else:
			event.Skip()

	def on_model_context_menu(self, event: wx.ContextMenuEvent | None):
		"""Handle context menu events for model list control.

		Args:
			event: The context menu event triggering the model context menu event
		"""
		menu = wx.Menu()
		item = wx.MenuItem(
			menu,
			wx.ID_ANY,
			# Translators: This is a label for a context menu item
			_("Show details") + " (Enter)",
		)
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.on_show_model_details, item)
		self.model_list.PopupMenu(menu)
		menu.Destroy()

	def on_show_model_details(self, event: wx.CommandEvent | None):
		"""Show model details dialog.

		Args:
			event: The command event triggering the model details dialog
		"""
		from .read_only_message_dialog import ReadOnlyMessageDialog

		model = self.current_model
		if not model:
			return
		dlg = ReadOnlyMessageDialog(
			self,
			# Translators: This is a label for a title dialog
			title=_("Model details"),
			message=model.display_details,
		)
		dlg.ShowModal()
		dlg.Destroy()

	def create_web_search_widget(self):
		"""Create and configure the web search mode check box."""
		self.web_search_mode = wx.CheckBox(
			self,
			# Translators: This is a label for web search mode in the main window
			label=_("&Web search mode"),
		)
		self.web_search_mode.SetValue(False)

	def create_max_tokens_widget(self) -> wx.StaticText:
		"""Create and configure the max tokens spin control.

		Returns:
			The label widget for the max tokens control
		"""
		self.max_tokens_spin_label = wx.StaticText(
			self,
			# Translators: This is a label for max tokens in the main window
			label=_("Max to&kens:"),
		)
		self.max_tokens_spin_ctrl = wx.SpinCtrl(
			self, value="0", min=0, max=2000000
		)

	def create_temperature_widget(self) -> wx.StaticText:
		"""Create and configure the temperature spin control.

		Returns:
			The label widget for the temperature control
		"""
		self.temperature_spinner_label = wx.StaticText(
			self,
			# Translators: This is a label for temperature in the main window
			label=_("&Temperature:"),
		)
		self.temperature_spinner = FloatSpin(
			self,
			min_val=0.0,
			max_val=2.0,
			increment=0.01,
			value=0.5,
			digits=2,
			name="temperature",
		)
		float_spin_accessible = FloatSpinTextCtrlAccessible(
			win=self.temperature_spinner._textctrl,
			name=self.temperature_spinner_label.GetLabel().replace("&", ""),
		)
		self.temperature_spinner._textctrl.SetAccessible(float_spin_accessible)

	def create_top_p_widget(self) -> wx.StaticText:
		"""Create and configure the top P spin control.

		Returns:
			The label widget for the top P control
		"""
		self.top_p_spinner_label = wx.StaticText(
			self,
			# Translators: This is a label for top P in the main window
			label=_("Probabilit&y Mass (top P):"),
		)
		self.top_p_spinner = FloatSpin(
			self,
			min_val=0.0,
			max_val=1.0,
			increment=0.01,
			value=1.0,
			digits=2,
			name="Top P",
		)
		float_spin_accessible = FloatSpinTextCtrlAccessible(
			win=self.top_p_spinner._textctrl,
			name=self.top_p_spinner_label.GetLabel().replace("&", ""),
		)
		self.top_p_spinner._textctrl.SetAccessible(float_spin_accessible)

	def create_stream_widget(self):
		"""Create and configure the stream mode check box."""
		self.stream_mode = wx.CheckBox(
			self,
			# Translators: This is a label for stream mode in the main window
			label=_("&Stream mode"),
		)
		self.stream_mode.SetValue(True)

	def get_effective_show_reasoning_blocks(self) -> bool:
		"""Effective value: per-tab override if set, else default from config."""
		if self._show_reasoning_blocks_override is not None:
			return self._show_reasoning_blocks_override
		return config.conf().conversation.show_reasoning_blocks

	def create_show_reasoning_blocks_widget(self):
		"""Create checkbox to show/hide reasoning (think) blocks in responses.

		Always visible. Per-tab override; default comes from Preferences.
		"""
		self.show_reasoning_blocks = wx.CheckBox(
			self,
			# Translators: Label for showing reasoning blocks in the main window
			label=_("Show &reasoning blocks in responses"),
		)
		self.show_reasoning_blocks.SetValue(
			self.get_effective_show_reasoning_blocks()
		)
		self.show_reasoning_blocks.Bind(
			wx.EVT_CHECKBOX, self._on_show_reasoning_blocks_change
		)

	def _on_show_reasoning_blocks_change(self, event: wx.Event | None):
		"""Set per-tab override and refresh message display."""
		self._show_reasoning_blocks_override = (
			self.show_reasoning_blocks.GetValue()
		)
		if hasattr(self, "refresh_messages"):
			self.refresh_messages(need_clear=True, preserve_prompt=True)

	def create_audio_output_group(self):
		"""Create grouped audio output settings (modality, voice, format, speed).

		Returns a StaticBoxSizer containing the audio output widgets. Add to
		layout after model list. Visibility controlled by update_parameter_controls_visibility.
		"""
		# Translators: Group label for audio output settings
		box = wx.StaticBox(self, label=_("Audio output"))
		sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
		self.create_output_modality_widget()
		sizer.Add(self.output_modality_label, 0, wx.ALL, 2)
		sizer.Add(self.output_modality_choice, 0, wx.ALL | wx.EXPAND, 2)
		self.output_modality_choice.Bind(
			wx.EVT_CHOICE, lambda e: self.update_parameter_controls_visibility()
		)
		self.create_audio_voice_widget()
		sizer.Add(self.audio_voice_label, 0, wx.ALL, 2)
		sizer.Add(self.audio_voice_choice, 0, wx.ALL | wx.EXPAND, 2)

		self.audio_output_group_box = box
		self.audio_output_group_sizer = sizer
		return sizer

	def create_output_modality_widget(self):
		"""Create output modality choice (text vs audio) for gpt-audio models."""
		self.output_modality_label = wx.StaticText(
			self,
			# Translators: Label for output modality (text or audio response)
			label=_("Output modality:"),
		)
		self.output_modality_choice = wx.Choice(
			self, choices=[_("Text"), _("Audio")]
		)
		self.output_modality_choice.SetSelection(0)

	def create_audio_voice_widget(self):
		"""Create voice selection for audio output.

		Initial choices are minimal; populated from engine in
		_apply_parameter_visibility_state when model supports audio.
		"""
		self.audio_voice_label = wx.StaticText(
			self,
			# Translators: Label for voice selection in audio output
			label=_("Audio voice:"),
		)
		self.audio_voice_choice = wx.Choice(self, choices=[_("Alloy")])
		self.audio_voice_choice.SetSelection(0)

	def create_reasoning_widget(self):
		"""Create reasoning mode checkbox and provider-adaptive controls."""
		self.reasoning_mode = wx.CheckBox(
			self,
			# Translators: Label for enabling reasoning/thinking mode
			label=_("Enable &reasoning mode"),
		)
		self.reasoning_mode.SetValue(False)
		self.reasoning_mode.Bind(
			wx.EVT_CHECKBOX, self._on_reasoning_mode_change
		)
		self.reasoning_adaptive = wx.CheckBox(
			self,
			# Translators: Use adaptive thinking (Anthropic Claude 4.6+)
			label=_("Use adaptive thinking"),
		)
		self.reasoning_adaptive.SetValue(False)
		self.reasoning_adaptive.Bind(
			wx.EVT_CHECKBOX, self._on_reasoning_mode_change
		)
		self.reasoning_budget_label = wx.StaticText(
			self,
			# Translators: Label for reasoning budget tokens
			label=_("Thinking budget (tokens):"),
		)
		self.reasoning_budget_spin = wx.SpinCtrl(
			self, value="16000", min=0, max=128000
		)
		self.reasoning_effort_label = wx.StaticText(
			self,
			# Translators: Label for reasoning effort level (OpenAI, xAI)
			label=_("Reasoning effort:"),
		)
		self.reasoning_effort_choice = wx.Choice(
			self, choices=[_("Low"), _("Medium"), _("High")]
		)
		self.reasoning_effort_choice.SetSelection(1)  # Medium

	def _on_reasoning_mode_change(self, event: wx.Event | None):
		"""Update visibility of provider-specific reasoning controls."""
		self.update_parameter_controls_visibility()

	def apply_profile(
		self,
		profile: Optional[config.ConversationProfile],
		fall_back_default_account: bool = False,
	):
		"""Apply all settings from a conversation profile.

		Args:
			profile: Conversation profile to apply
			fall_back_default_account (bool): Whether to use default account as fallback
		"""
		if fall_back_default_account and not profile:
			log.debug("no profile, select default account")
			self.select_default_account()
			return
		self.system_prompt_txt.SetValue(profile.system_prompt)
		self.set_account_and_model_from_profile(
			profile, fall_back_default_account
		)
		if profile.max_tokens is not None:
			self.max_tokens_spin_ctrl.SetValue(profile.max_tokens)
		if profile.temperature is not None:
			self.temperature_spinner.SetValue(profile.temperature)
		if profile.top_p is not None:
			self.top_p_spinner.SetValue(profile.top_p)
		self.stream_mode.SetValue(profile.stream_mode)
		self._apply_profile_audio(profile)
		self._apply_profile_reasoning(profile)
		self.update_parameter_controls_visibility()

	def _apply_profile_audio(self, profile: config.ConversationProfile) -> None:
		"""Apply audio output settings from profile."""
		if hasattr(self, "output_modality_choice"):
			modality = getattr(profile, "output_modality", "text")
			self.output_modality_choice.SetSelection(
				1 if modality == "audio" else 0
			)
		if hasattr(self, "audio_voice_choice"):
			voice = getattr(profile, "audio_voice", "alloy")
			engine = self.current_engine
			model = self.current_model
			voices = ("alloy",)
			if engine and model:
				spec = engine.get_audio_output_spec(model)
				if spec:
					voices = spec.voices
			idx = voices.index(voice) if voice in voices else 0
			self.audio_voice_choice.SetSelection(idx)

	def _apply_profile_reasoning(
		self, profile: config.ConversationProfile
	) -> None:
		"""Apply reasoning settings from profile."""
		if not hasattr(self, "reasoning_mode"):
			return
		self.reasoning_mode.SetValue(profile.reasoning_mode)
		self.reasoning_adaptive.SetValue(profile.reasoning_adaptive)
		if profile.reasoning_budget_tokens is not None:
			self.reasoning_budget_spin.SetValue(profile.reasoning_budget_tokens)
		if profile.reasoning_effort is not None:
			engine = self.current_engine
			model = self.current_model
			options = ("low", "medium", "high")
			if engine and model:
				spec = engine.get_reasoning_ui_spec(model)
				if spec.effort_options:
					options = spec.effort_options
			val = profile.reasoning_effort.lower()
			idx = options.index(val) if val in options else len(options) - 1
			self.reasoning_effort_choice.SetSelection(idx)

	def update_parameter_controls_visibility(self):
		"""Show/hide parameter controls based on selected model and advanced mode.

		Delegates to presenter for business logic; applies result to widgets.
		"""
		advanced_mode = config.conf().general.advanced_mode
		model = self.current_model
		engine = self.current_engine

		reasoning_mode_checked = False
		reasoning_adaptive_checked = False
		output_modality_audio = False
		if hasattr(self, "reasoning_mode"):
			reasoning_mode_checked = bool(self.reasoning_mode.GetValue())
		if hasattr(self, "reasoning_adaptive"):
			reasoning_adaptive_checked = bool(
				self.reasoning_adaptive.GetValue()
			)
		if hasattr(self, "output_modality_choice"):
			output_modality_audio = (
				self.output_modality_choice.GetSelection() == 1
			)

		state = self.base_conv_presenter.get_parameter_visibility_state(
			advanced_mode,
			model,
			engine,
			reasoning_mode_checked=reasoning_mode_checked,
			reasoning_adaptive_checked=reasoning_adaptive_checked,
			output_modality_audio=output_modality_audio,
		)
		self._apply_parameter_visibility_state(state)
		self.Layout()

	def _apply_parameter_visibility_state(
		self, state: ParameterVisibilityState
	) -> None:
		"""Apply visibility state to widgets. Thin view layer."""
		for ctrl in (self.temperature_spinner_label, self.temperature_spinner):
			ctrl.Enable(state.temperature_visible)
			ctrl.Show(state.temperature_visible)
		for ctrl in (self.top_p_spinner_label, self.top_p_spinner):
			ctrl.Enable(state.top_p_visible)
			ctrl.Show(state.top_p_visible)
		for ctrl in (self.max_tokens_spin_label, self.max_tokens_spin_ctrl):
			ctrl.Enable(state.max_tokens_visible)
			ctrl.Show(state.max_tokens_visible)
		self.stream_mode.Enable(state.stream_visible)
		self.stream_mode.Show(state.stream_visible)

		self._apply_audio_visibility(state)
		self._apply_web_search_visibility(state)
		self._apply_reasoning_visibility(state)

	def _apply_audio_visibility(self, state: ParameterVisibilityState) -> None:
		"""Apply audio output visibility state."""
		if not hasattr(self, "audio_output_group_box"):
			return
		visible = state.output_modality_visible
		self.audio_output_group_box.Show(visible)
		for ctrl in (self.output_modality_label, self.output_modality_choice):
			ctrl.Enable(visible)
			ctrl.Show(visible)
		for ctrl in (self.audio_voice_label, self.audio_voice_choice):
			ctrl.Enable(visible and state.audio_settings_visible)
			ctrl.Show(visible and state.audio_settings_visible)
		if visible and state.voice_options:
			voices = state.voice_options
			display = [_(v.capitalize()) for v in voices]
			sel = self.audio_voice_choice.GetSelection()
			old_val = voices[sel] if 0 <= sel < len(voices) else voices[0]
			self.audio_voice_choice.SetItems(display)
			idx = voices.index(old_val) if old_val in voices else 0
			self.audio_voice_choice.SetSelection(idx)

	def _apply_web_search_visibility(
		self, state: ParameterVisibilityState
	) -> None:
		"""Apply web search visibility state."""
		if hasattr(self, "web_search_mode"):
			self.web_search_mode.Enable(state.web_search_visible)
			self.web_search_mode.Show(state.web_search_visible)

	def _apply_reasoning_visibility(
		self, state: ParameterVisibilityState
	) -> None:
		"""Apply reasoning controls visibility state."""
		if not hasattr(self, "reasoning_mode"):
			return
		self.reasoning_mode.Enable(state.reasoning_mode_visible)
		self.reasoning_mode.Show(state.reasoning_mode_visible)
		self.reasoning_adaptive.Enable(state.reasoning_adaptive_visible)
		self.reasoning_adaptive.Show(state.reasoning_adaptive_visible)
		self.reasoning_budget_label.Enable(state.reasoning_budget_visible)
		self.reasoning_budget_label.Show(state.reasoning_budget_visible)
		self.reasoning_budget_spin.Enable(state.reasoning_budget_visible)
		self.reasoning_budget_spin.Show(state.reasoning_budget_visible)

		for ctrl in (self.reasoning_effort_label, self.reasoning_effort_choice):
			ctrl.Enable(state.reasoning_effort_visible)
			ctrl.Show(state.reasoning_effort_visible)

		if state.reasoning_effort_visible and state.effort_display:
			display = [_(s) for s in state.effort_display]
			try:
				sel = self.reasoning_effort_choice.GetSelection()
				old_val = state.effort_options[
					min(sel, len(state.effort_options) - 1)
				]
			except IndexError, TypeError:
				old_val = state.effort_options[-1]
			self.reasoning_effort_choice.SetItems(display)
			idx = (
				state.effort_options.index(old_val)
				if old_val in state.effort_options
				else len(state.effort_options) - 1
			)
			self.reasoning_effort_choice.SetSelection(idx)
			self.reasoning_effort_label.SetLabel(_(state.effort_label))

	def adjust_advanced_mode_setting(self):
		"""Update UI controls visibility based on advanced mode and model support."""
		self.update_parameter_controls_visibility()
