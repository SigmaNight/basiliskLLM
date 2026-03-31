"""Base conversation module providing core conversation UI components and functionality."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import wx
from more_itertools import first, locate
from wx.lib.agw.floatspin import FloatSpin

import basilisk.config as config
from basilisk.config import AccountSource, ModelSortKeyEnum
from basilisk.presenters.base_conversation_presenter import (
	BaseConversationPresenter,
	ParameterVisibilityState,
)
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_engine.dynamic_model_loader import invalidate_model_cache
from basilisk.services.account_model_service import AccountModelService

from .accessible import AccessibleWithHelp
from .account_dialog import EditAccountDialog
from .int_spin_ctrl import IntSpinCtrl
from .model_details_dialog import ModelDetailsDialog

if TYPE_CHECKING:
	from basilisk.provider_engine.base_engine import BaseEngine

log = logging.getLogger(__name__)

_REVERSE_DEFAULT_SORT_KEYS = frozenset(
	(
		ModelSortKeyEnum.RELEASE_DATE,
		ModelSortKeyEnum.MAX_OUTPUT,
		ModelSortKeyEnum.CONTEXT_WINDOW,
	)
)


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
		self._display_models: list[ProviderAIModel] = []
		self._model_sort_key = ModelSortKeyEnum.NONE
		self._model_sort_reverse = False

	def _get_effective_model_sort(self) -> tuple[str, bool]:
		"""Get effective sort key and reverse from account override or preference.

		Returns:
			Tuple of (sort_key, reverse). Account override takes precedence over
			preference default.
		"""
		account = self.current_account
		if account and account.model_sort_key is not None:
			reverse = (
				account.model_sort_reverse
				if account.model_sort_reverse is not None
				else False
			)
			return (account.model_sort_key, reverse)
		conv = config.conf().conversation
		return (conv.model_sort_key, conv.model_sort_reverse)

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
		self.account_combo.Bind(
			wx.EVT_CONTEXT_MENU, self.on_account_combo_context_menu
		)
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

	def _refresh_account_combo(self) -> bool:
		"""Refresh the account combo. Returns True if selection fell back to first."""
		account_index = self.account_combo.GetSelection()
		account_id = (
			config.accounts()[account_index].id
			if account_index != wx.NOT_FOUND
			else None
		)
		self.account_combo.Clear()
		self.account_combo.AppendItems(self.get_display_accounts(True))
		account_index = first(
			locate(config.accounts(), lambda a: a.id == account_id),
			wx.NOT_FOUND,
		)
		if account_index != wx.NOT_FOUND:
			self.account_combo.SetSelection(account_index)
		elif self.account_combo.GetCount() > 0:
			self.account_combo.SetSelection(0)
		self.Layout()
		return (
			account_index == wx.NOT_FOUND and self.account_combo.GetCount() > 0
		)

	def on_account_combo_context_menu(self, event: wx.ContextMenuEvent) -> None:
		"""Show context menu for account combo."""
		account = self.current_account
		menu = wx.Menu()
		edit_item = menu.Append(wx.ID_ANY, _("Edit account"))
		can_edit = (
			account is not None and account.source != AccountSource.ENV_VAR
		)
		menu.Enable(edit_item.GetId(), can_edit)
		if can_edit:
			self.Bind(
				wx.EVT_MENU,
				lambda e: self._edit_account_from_combo(account),
				id=edit_item.GetId(),
			)
		menu.AppendSeparator()
		default_item = menu.Append(wx.ID_ANY, _("Set as default"))
		accounts = config.accounts()
		can_set_default = accounts.can_set_as_default(account)
		menu.Enable(default_item.GetId(), can_set_default)
		if can_set_default:
			self.Bind(
				wx.EVT_MENU,
				lambda e: self._set_default_account_from_combo(account),
				id=default_item.GetId(),
			)
		self.account_combo.PopupMenu(menu, event.GetPosition())
		menu.Destroy()

	def _set_default_account_from_combo(self, account: config.Account) -> None:
		accounts = config.accounts()
		accounts.set_default_account(account)
		accounts.save()

	def _edit_account_from_combo(self, account: config.Account) -> None:
		accounts = config.accounts()
		index = next(locate(accounts, lambda a: a.id == account.id), None)
		if index is None:
			return
		dialog = EditAccountDialog(
			self, _("Edit account"), account=account.model_copy(deep=True)
		)
		if dialog.ShowModal() == wx.ID_OK:
			accounts[index] = dialog.account
			accounts.save()
			self._refresh_account_combo()
			self.on_account_change(None)
		dialog.Destroy()

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
		self._model_sort_key, self._model_sort_reverse = (
			self._get_effective_model_sort()
		)
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

	def create_settings_section(self):
		"""Create model, reasoning, tools, output - all settings in one sizer.

		Returns a BoxSizer. Use in conversation tab and edit block dialog
		to avoid duplicating the settings layout.
		"""
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.create_model_section()
		sizer.Add(self.model_section_sizer, 0, wx.EXPAND)
		self.create_audio_output_group()
		sizer.Add(self.audio_output_group_sizer, 0, wx.EXPAND)
		self.create_reasoning_group()
		sizer.Add(self.reasoning_group_sizer, 0, wx.EXPAND)
		self.create_tools_group()
		sizer.Add(self.tools_group_sizer, 0, wx.EXPAND)
		self.create_output_group()
		sizer.Add(self.output_group_sizer, 0, wx.EXPAND)
		self.settings_section_sizer = sizer
		return sizer

	def create_model_section(self):
		"""Create model selection (label + list). No group box - single control.

		Returns a BoxSizer containing the model list. Add to layout after
		account row.
		"""
		sizer = wx.BoxSizer(wx.VERTICAL)
		label = wx.StaticText(
			self,
			# Translators: Label for model selection list
			label=_("M&odels:"),
		)
		sizer.Add(label, 0, wx.ALL, 2)
		self.create_model_widget()
		sizer.Add(self.model_list, 0, wx.ALL | wx.EXPAND, 2)

		self.model_section_sizer = sizer
		return sizer

	def create_output_group(self):
		"""Create output/generation parameters group (max tokens, temperature, etc.).

		Returns a StaticBoxSizer. Visibility controlled by
		update_parameter_controls_visibility.
		"""
		# Translators: Group label for response generation parameters
		box = wx.StaticBox(self, label=_("Output"))
		sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
		output_panel = wx.Panel(self)
		output_panel.Bind(wx.EVT_CONTEXT_MENU, self._on_output_context_menu)
		inner = wx.BoxSizer(wx.VERTICAL)
		self.create_max_tokens_widget(output_panel)
		inner.Add(self.max_tokens_spin_label, 0, wx.ALL, 2)
		inner.Add(self.max_tokens_spin_ctrl, 0, wx.ALL | wx.EXPAND, 2)
		self.create_temperature_widget(output_panel)
		inner.Add(self.temperature_spinner_label, 0, wx.ALL, 2)
		inner.Add(self.temperature_spinner, 0, wx.ALL | wx.EXPAND, 2)
		self.create_top_p_widget(output_panel)
		inner.Add(self.top_p_spinner_label, 0, wx.ALL, 2)
		inner.Add(self.top_p_spinner, 0, wx.ALL | wx.EXPAND, 2)
		self.create_frequency_penalty_widget(output_panel)
		inner.Add(self.frequency_penalty_label, 0, wx.ALL, 2)
		inner.Add(self.frequency_penalty_spinner, 0, wx.ALL | wx.EXPAND, 2)
		self.create_presence_penalty_widget(output_panel)
		inner.Add(self.presence_penalty_label, 0, wx.ALL, 2)
		inner.Add(self.presence_penalty_spinner, 0, wx.ALL | wx.EXPAND, 2)
		self.create_seed_widget(output_panel)
		inner.Add(self.seed_label, 0, wx.ALL, 2)
		inner.Add(self.seed_spin_ctrl, 0, wx.ALL | wx.EXPAND, 2)
		self.create_top_k_widget(output_panel)
		inner.Add(self.top_k_label, 0, wx.ALL, 2)
		inner.Add(self.top_k_spin_ctrl, 0, wx.ALL | wx.EXPAND, 2)
		self.create_stop_widget(output_panel)
		inner.Add(self.stop_label, 0, wx.ALL, 2)
		inner.Add(self.stop_text_ctrl, 0, wx.ALL | wx.EXPAND, 2)
		self.create_stream_widget(output_panel)
		inner.Add(self.stream_mode, 0, wx.ALL, 2)
		output_panel.SetSizer(inner)
		sizer.Add(output_panel, 0, wx.EXPAND)

		self.output_group_box = box
		self.output_group_panel = output_panel
		self.output_group_sizer = sizer
		return sizer

	def _on_output_context_menu(self, event: wx.ContextMenuEvent) -> None:
		"""Show context menu for output params (reset to defaults)."""
		menu = wx.Menu()
		item = wx.MenuItem(
			menu,
			wx.ID_ANY,
			# Translators: Context menu item to reset generation params to model defaults
			_("Reset to model defaults"),
		)
		menu.Append(item)
		item.Enable(self.current_model is not None)
		menu.Bind(wx.EVT_MENU, self._on_reset_to_model_defaults, item)
		event.GetEventObject().PopupMenu(menu)
		menu.Destroy()

	def _reset_to_model_defaults(self) -> None:
		"""Reset all generation params to the selected model's defaults."""
		model = self.current_model
		if not model:
			return
		self.temperature_spinner.SetMax(model.max_temperature)
		self.temperature_spinner.SetValue(model.default_temperature)
		self.max_tokens_spin_ctrl.SetMax(model.effective_max_output_tokens)
		self.max_tokens_spin_ctrl.SetValue(0)
		for param, default, conv, ctrl_attr in self._OUTPUT_PARAM_DEFAULTS:
			val = model.get_default_param(param, default)
			getattr(self, ctrl_attr).SetValue(
				conv(val) if val is not None else default
			)
		self.stop_text_ctrl.SetValue("")

	def _on_reset_to_model_defaults(self, event: wx.CommandEvent) -> None:
		"""Handle context menu selection to reset to model defaults."""
		self._reset_to_model_defaults()

	def create_reasoning_group(self):
		"""Create reasoning/thinking configuration group.

		Returns a StaticBoxSizer. Visibility controlled by
		update_parameter_controls_visibility.
		"""
		# Translators: Group label for reasoning/thinking settings
		box = wx.StaticBox(self, label=_("Reasoning"))
		sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
		self.create_reasoning_widget()
		sizer.Add(self.reasoning_mode, 0, wx.ALL, 2)
		sizer.Add(self.reasoning_adaptive, 0, wx.ALL, 2)
		sizer.Add(self.reasoning_budget_label, 0, wx.ALL, 2)
		sizer.Add(self.reasoning_budget_spin, 0, wx.ALL | wx.EXPAND, 2)
		sizer.Add(self.reasoning_effort_label, 0, wx.ALL, 2)
		sizer.Add(self.reasoning_effort_choice, 0, wx.ALL | wx.EXPAND, 2)

		self.reasoning_group_box = box
		self.reasoning_group_sizer = sizer
		return sizer

	def create_tools_group(self):
		"""Create tools group (web search, etc.).

		Returns a StaticBoxSizer. Visibility controlled by
		update_parameter_controls_visibility.
		"""
		# Translators: Group label for model tools (web search, etc.)
		box = wx.StaticBox(self, label=_("Tools"))
		sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
		self.create_web_search_widget()
		sizer.Add(self.web_search_mode, 0, wx.ALL, 2)

		self.tools_group_box = box
		self.tools_group_sizer = sizer
		return sizer

	def create_model_widget(self) -> None:
		"""Create and configure the model selection list control."""
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

	def _sort_key_for_model(self, model: ProviderAIModel, key: str):
		"""Return sort key for a model. Used for sorting."""
		if key == ModelSortKeyEnum.NAME:
			return (model.display_name or model.id or "").lower()
		if key == ModelSortKeyEnum.RELEASE_DATE:
			return model.created
		if key == ModelSortKeyEnum.MAX_OUTPUT:
			return model.max_output_tokens if model.max_output_tokens > 0 else 0
		if key == ModelSortKeyEnum.CONTEXT_WINDOW:
			return model.context_window
		return model.display_name or model.id or ""

	def update_model_list(self):
		"""Update the model list with current engine's available models."""
		engine = self.current_engine
		if not engine:
			self._display_models = []
			self.model_list.DeleteAllItems()
			return
		sort_key = self._model_sort_key
		models = list(engine.models)
		if sort_key == ModelSortKeyEnum.NONE:
			reverse = self._model_sort_reverse
			self._display_models = list(reversed(models)) if reverse else models
		else:
			reverse_default = sort_key in _REVERSE_DEFAULT_SORT_KEYS
			reverse = reverse_default != self._model_sort_reverse
			self._display_models = sorted(
				models,
				key=lambda m: self._sort_key_for_model(m, sort_key),
				reverse=reverse,
			)
		self.model_list.DeleteAllItems()
		for model in self._display_models:
			self.model_list.Append(model.display_model)

	def set_model_list(self, model: Optional[ProviderAIModel]):
		"""Set the selected model in the model list.

		Args:
			model: Model to select
		"""
		if not self._display_models:
			return
		index = wx.NOT_FOUND
		if model:
			index = next(
				locate(self._display_models, lambda m: m == model), wx.NOT_FOUND
			)
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
		model_index = self.model_list.GetFirstSelected()
		if model_index == wx.NOT_FOUND or model_index >= len(
			self._display_models
		):
			return None
		return self._display_models[model_index]

	# (param_name, default, converter, ctrl_attr) for on_model_change from JSON
	_OUTPUT_PARAM_DEFAULTS = (
		("top_p", 1.0, float, "top_p_spinner"),
		("frequency_penalty", 0.0, float, "frequency_penalty_spinner"),
		("presence_penalty", 0.0, float, "presence_penalty_spinner"),
		("seed", 0, int, "seed_spin_ctrl"),
		("top_k", 0, int, "top_k_spin_ctrl"),
	)
	# (profile_attr, ctrl_attr) for apply_profile
	_PROFILE_TO_CTRL = (
		("max_tokens", "max_tokens_spin_ctrl"),
		("temperature", "temperature_spinner"),
		("top_p", "top_p_spinner"),
		("frequency_penalty", "frequency_penalty_spinner"),
		("presence_penalty", "presence_penalty_spinner"),
		("seed", "seed_spin_ctrl"),
		("top_k", "top_k_spin_ctrl"),
	)

	def on_model_change(self, event: wx.Event | None):
		"""Handle model selection change events.

		Args:
			event: The event triggering the model change
		"""
		if self.current_model:
			self._reset_to_model_defaults()
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
		"""Handle key down: Enter = show details, F5 = refresh models."""
		key = event.GetKeyCode()
		if key == wx.WXK_RETURN:
			self.on_show_model_details(None)
		elif key == wx.WXK_F5:
			self.on_refresh_models(None)
		else:
			event.Skip()

	def on_model_context_menu(self, event: wx.ContextMenuEvent | None):
		"""Handle context menu for model list."""
		menu = wx.Menu()
		item = wx.MenuItem(
			menu,
			wx.ID_ANY,
			# Translators: This is a label for a context menu item
			_("Show details") + " (Enter)",
		)
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.on_show_model_details, item)
		item = wx.MenuItem(
			menu,
			wx.ID_ANY,
			# Translators: This is a label for a context menu item to refresh the models list
			_("Refresh models") + " (F5)",
		)
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.on_refresh_models, item)
		sort_menu = wx.Menu()
		# Translators: Submenu label for sort options
		sort_labels = {
			# Translators: None = use sort order from JSON/source (no custom sort)
			"none": _("None"),
			"name": _("Name"),
			"release_date": _("Release date"),
			"max_output": _("Max output"),
			"context_window": _("Context window"),
		}
		model_sort_keys = (
			"none",
			"name",
			"release_date",
			"max_output",
			"context_window",
		)
		current_key = self._model_sort_key
		for key in model_sort_keys:
			sort_item = sort_menu.AppendCheckItem(
				wx.ID_ANY, sort_labels.get(key, key)
			)
			sort_item.Check(key == current_key)
			self.Bind(
				wx.EVT_MENU,
				lambda e, k=key: self._on_model_sort_by(k),
				sort_item,
			)
		sort_menu.AppendSeparator()
		reverse_item = sort_menu.AppendCheckItem(
			wx.ID_ANY,
			# Translators: Checkable item to reverse the current sort order
			_("Reverse order"),
		)
		reverse_item.Check(self._model_sort_reverse)
		self.Bind(wx.EVT_MENU, self._on_model_sort_reverse, reverse_item)
		menu.AppendSubMenu(
			sort_menu,
			# Translators: Submenu label for model list sort options
			_("Sort by"),
		)
		self.model_list.PopupMenu(menu)
		menu.Destroy()

	def _on_model_sort_by(self, sort_key: str):
		"""Handle sort-by selection from context menu."""
		if self._model_sort_key == sort_key:
			return
		self._model_sort_key = sort_key
		self._refresh_model_list_preserving_selection()

	def _on_model_sort_reverse(self, event: wx.CommandEvent | None):
		"""Handle reverse sort toggle from context menu."""
		self._model_sort_reverse = not self._model_sort_reverse
		self._refresh_model_list_preserving_selection()

	def _refresh_model_list_preserving_selection(self):
		"""Refresh model list and restore selection by model id."""
		model_id = self.current_model.id if self.current_model else None
		self.update_model_list()
		model = (
			next((m for m in self._display_models if m.id == model_id), None)
			if model_id
			else None
		)
		self.set_model_list(model)

	def on_refresh_models(self, event: wx.CommandEvent | None):
		"""Refresh the models list."""
		engine = self.current_engine
		if not engine:
			return
		model_id = self.current_model.id if self.current_model else None
		if url := getattr(engine, "MODELS_JSON_URL", None):
			invalidate_model_cache(url)
		if "models" in engine.__dict__:
			del engine.__dict__["models"]
		self.update_model_list()
		model = (
			next((m for m in engine.models if m.id == model_id), None)
			if model_id
			else None
		)
		self.set_model_list(model)

	def on_show_model_details(self, event: wx.CommandEvent | None):
		"""Show model details dialog.

		Args:
			event: The command event triggering the model details dialog
		"""
		model = self.current_model
		if not model:
			return
		dlg = ModelDetailsDialog(self, model)
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

	def _create_float_spin_with_accessibility(
		self,
		label: str,
		min_val: float,
		max_val: float,
		value: float,
		name: str,
		help_text: str | None = None,
		*,
		digits: int = 2,
		increment: float = 0.01,
		parent: wx.Window | None = None,
	) -> tuple[wx.StaticText, FloatSpin]:
		"""Create label + FloatSpin with accessibility, matching temperature/top_p."""
		p = parent or self
		label_ctrl = wx.StaticText(p, label=label)
		spinner = FloatSpin(
			p,
			min_val=min_val,
			max_val=max_val,
			increment=increment,
			value=value,
			digits=digits,
			name=name,
		)
		spinner._textctrl.SetAccessible(
			AccessibleWithHelp(
				win=spinner._textctrl,
				name=label_ctrl.GetLabel().replace("&", ""),
				help_text=help_text,
			)
		)
		spinner.SetToolTip(help_text or "")
		return label_ctrl, spinner

	def _create_int_spin_with_accessibility(
		self,
		label: str,
		min_val: int,
		max_val: int,
		value: int,
		tooltip_key: str,
		parent: wx.Window | None = None,
	) -> tuple[wx.StaticText, IntSpinCtrl]:
		"""Create label + IntSpinCtrl with accessibility."""
		p = parent or self
		label_ctrl = wx.StaticText(p, label=label)
		help_text = self._OUTPUT_PARAM_TOOLTIPS[tooltip_key]
		ctrl = IntSpinCtrl(
			p,
			value=value,
			min_val=min_val,
			max_val=max_val,
			help_text=help_text,
			label=label_ctrl.GetLabel(),
		)
		ctrl.SetToolTip(help_text)
		return label_ctrl, ctrl

	# Tooltips for generation params (shown on hover)
	_OUTPUT_PARAM_TOOLTIPS = {
		"max_tokens_spin_ctrl": _(
			"Maximum length of the response. 0 = use model default."
		),
		"temperature_spinner": _(
			"Controls randomness. Lower = more focused, higher = more random."
		),
		"top_p_spinner": _(
			"Nucleus sampling. Lower = more deterministic, higher = more diverse."
		),
		"frequency_penalty_spinner": _(
			"Reduces repetition based on token frequency. Negative = allow more."
		),
		"presence_penalty_spinner": _(
			"Reduces repetition of tokens that have appeared. Negative = allow more."
		),
		"seed_spin_ctrl": _(
			"Random seed for reproducibility. 0 = random each time."
		),
		"top_k_spin_ctrl": _(
			"Consider only the top K most likely tokens. 0 = model default."
		),
		"stop_text_ctrl": _(
			"Text sequences that stop generation. One per line or comma-separated."
		),
		"stream_mode": _("Stream the response as it is generated."),
	}

	def create_max_tokens_widget(self, parent: wx.Window | None = None) -> None:
		"""Create and configure the max tokens spin control."""
		self.max_tokens_spin_label, self.max_tokens_spin_ctrl = (
			self._create_int_spin_with_accessibility(
				label=_("Max to&kens:"),
				min_val=0,
				max_val=2000000,
				value=0,
				tooltip_key="max_tokens_spin_ctrl",
				parent=parent,
			)
		)

	def create_temperature_widget(
		self, parent: wx.Window | None = None
	) -> wx.StaticText:
		"""Create and configure the temperature spin control."""
		help_text = self._OUTPUT_PARAM_TOOLTIPS["temperature_spinner"]
		self.temperature_spinner_label, self.temperature_spinner = (
			self._create_float_spin_with_accessibility(
				label=_("&Temperature:"),
				min_val=0.0,
				max_val=2.0,
				value=0.5,
				name="temperature",
				help_text=help_text,
				parent=parent,
			)
		)
		return self.temperature_spinner_label

	def create_top_p_widget(
		self, parent: wx.Window | None = None
	) -> wx.StaticText:
		"""Create and configure the top P spin control."""
		help_text = self._OUTPUT_PARAM_TOOLTIPS["top_p_spinner"]
		self.top_p_spinner_label, self.top_p_spinner = (
			self._create_float_spin_with_accessibility(
				label=_("&Top P:"),
				min_val=0.0,
				max_val=1.0,
				value=1.0,
				name="Top P",
				help_text=help_text,
				parent=parent,
			)
		)
		return self.top_p_spinner_label

	def create_frequency_penalty_widget(
		self, parent: wx.Window | None = None
	) -> None:
		"""Create frequency penalty control. Default 0, range -2 to 2 (OpenAI)."""
		help_text = self._OUTPUT_PARAM_TOOLTIPS["frequency_penalty_spinner"]
		self.frequency_penalty_label, self.frequency_penalty_spinner = (
			self._create_float_spin_with_accessibility(
				label=_("&Frequency penalty:"),
				min_val=-2.0,
				max_val=2.0,
				value=0.0,
				name="frequency_penalty",
				help_text=help_text,
				parent=parent,
			)
		)

	def create_presence_penalty_widget(
		self, parent: wx.Window | None = None
	) -> None:
		"""Create presence penalty control. Default 0, range -2 to 2 (OpenAI)."""
		help_text = self._OUTPUT_PARAM_TOOLTIPS["presence_penalty_spinner"]
		self.presence_penalty_label, self.presence_penalty_spinner = (
			self._create_float_spin_with_accessibility(
				label=_("&Presence penalty:"),
				min_val=-2.0,
				max_val=2.0,
				value=0.0,
				name="presence_penalty",
				help_text=help_text,
				parent=parent,
			)
		)

	def create_seed_widget(self, parent: wx.Window | None = None) -> None:
		"""Create seed control. 0 = not set; positive = deterministic."""
		self.seed_label, self.seed_spin_ctrl = (
			self._create_int_spin_with_accessibility(
				label=_("&Seed:"),
				min_val=0,
				max_val=2147483647,
				value=0,
				tooltip_key="seed_spin_ctrl",
				parent=parent,
			)
		)

	def create_top_k_widget(self, parent: wx.Window | None = None) -> None:
		"""Create top-k control. 0 = not set."""
		self.top_k_label, self.top_k_spin_ctrl = (
			self._create_int_spin_with_accessibility(
				label=_("&Top K:"),
				min_val=0,
				max_val=256,
				value=0,
				tooltip_key="top_k_spin_ctrl",
				parent=parent,
			)
		)

	def create_stop_widget(self, parent: wx.Window | None = None) -> None:
		"""Create stop sequences control. One per line or comma-separated."""
		p = parent or self
		self.stop_label = wx.StaticText(
			p,
			# Translators: Label for stop sequences
			label=_("&Stop sequences:"),
		)
		self.stop_text_ctrl = wx.TextCtrl(
			p, style=wx.TE_MULTILINE | wx.TE_WORDWRAP, size=(-1, 50)
		)
		help_text = self._OUTPUT_PARAM_TOOLTIPS["stop_text_ctrl"]
		self.stop_text_ctrl.SetToolTip(help_text)
		self.stop_text_ctrl.SetAccessible(
			AccessibleWithHelp(
				win=self.stop_text_ctrl,
				name=self.stop_label.GetLabel().replace("&", ""),
				help_text=help_text,
			)
		)

	def get_stop_sequences(self) -> list[str] | None:
		"""Parse stop sequences from text control. One per line, strip empty."""
		if not hasattr(self, "stop_text_ctrl"):
			return None
		text = self.stop_text_ctrl.GetValue().strip()
		if not text:
			return None
		sequences = [
			line.strip()
			for line in text.replace(",", "\n").splitlines()
			if line.strip()
		]
		return sequences if sequences else None

	def get_generation_params_from_view(self) -> dict:
		"""Return generation params from view controls for MessageBlock."""
		params = {
			"temperature": self.temperature_spinner.GetValue(),
			"top_p": self.top_p_spinner.GetValue(),
			"max_tokens": self.max_tokens_spin_ctrl.GetValue(),
			"frequency_penalty": self.frequency_penalty_spinner.GetValue(),
			"presence_penalty": self.presence_penalty_spinner.GetValue(),
			"stream": self.stream_mode.GetValue(),
		}
		seed_val = self.seed_spin_ctrl.GetValue()
		params["seed"] = seed_val if seed_val else None  # 0 = not set
		top_k_val = self.top_k_spin_ctrl.GetValue()
		params["top_k"] = top_k_val if top_k_val else None  # 0 = default
		params["stop"] = self.get_stop_sequences()
		return params

	def create_stream_widget(self, parent: wx.Window | None = None):
		"""Create and configure the stream mode check box."""
		p = parent or self
		self.stream_mode = wx.CheckBox(
			p,
			# Translators: This is a label for stream mode in the main window
			label=_("&Stream mode"),
		)
		self.stream_mode.SetValue(True)
		help_text = self._OUTPUT_PARAM_TOOLTIPS["stream_mode"]
		self.stream_mode.SetToolTip(help_text)
		self.stream_mode.SetAccessible(
			AccessibleWithHelp(
				win=self.stream_mode,
				name=self.stream_mode.GetLabel().replace("&", ""),
				help_text=help_text,
			)
		)

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
		"""Create voice selection for audio output."""
		self.audio_voice_label = wx.StaticText(
			self,
			# Translators: Label for voice selection in audio output
			label=_("Audio voice:"),
		)
		voices = [
			"alloy",
			"ash",
			"ballad",
			"coral",
			"echo",
			"fable",
			"onyx",
			"nova",
			"sage",
			"shimmer",
			"verse",
			"marin",
			"cedar",
		]
		self.audio_voice_choice = wx.Choice(
			self, choices=[v.capitalize() for v in voices]
		)
		self.audio_voice_choice.SetSelection(0)

	def get_effective_show_reasoning_blocks(self) -> bool:
		"""Return whether to show reasoning blocks (from config)."""
		return config.conf().conversation.show_reasoning_blocks

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
		# Apply generation params from profile when set
		for profile_attr, ctrl_attr in self._PROFILE_TO_CTRL:
			val = getattr(profile, profile_attr, None)
			if val is not None:
				getattr(self, ctrl_attr).SetValue(val)
		if getattr(profile, "stop", None):
			self.stop_text_ctrl.SetValue("\n".join(profile.stop))
		self.stream_mode.SetValue(profile.stream_mode)
		if hasattr(self, "output_modality_choice"):
			modality = getattr(profile, "output_modality", "text")
			self.output_modality_choice.SetSelection(
				1 if modality == "audio" else 0
			)
		if hasattr(self, "audio_voice_choice"):
			voice = getattr(profile, "audio_voice", "alloy")
			voices = [
				"alloy",
				"ash",
				"ballad",
				"coral",
				"echo",
				"fable",
				"onyx",
				"nova",
				"sage",
				"shimmer",
				"verse",
				"marin",
				"cedar",
			]
			idx = voices.index(voice) if voice in voices else 0
			self.audio_voice_choice.SetSelection(idx)
		if hasattr(self, "reasoning_mode"):
			self.reasoning_mode.SetValue(profile.reasoning_mode)
			self.reasoning_adaptive.SetValue(profile.reasoning_adaptive)
			if profile.reasoning_budget_tokens is not None:
				self.reasoning_budget_spin.SetValue(
					profile.reasoning_budget_tokens
				)
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
		self.update_parameter_controls_visibility()

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
			if val in options:
				self.reasoning_effort_choice.SetSelection(options.index(val))

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
		self._apply_output_visibility(state)
		self._apply_audio_visibility(state)
		self._apply_tools_visibility(state)
		self._apply_reasoning_visibility(state)

	# Output param visibility: (state_attr, label_attr, ctrl_attr)
	_OUTPUT_VISIBILITY = (
		(
			"temperature_visible",
			"temperature_spinner_label",
			"temperature_spinner",
		),
		("top_p_visible", "top_p_spinner_label", "top_p_spinner"),
		("max_tokens_visible", "max_tokens_spin_label", "max_tokens_spin_ctrl"),
		(
			"frequency_penalty_visible",
			"frequency_penalty_label",
			"frequency_penalty_spinner",
		),
		(
			"presence_penalty_visible",
			"presence_penalty_label",
			"presence_penalty_spinner",
		),
		("seed_visible", "seed_label", "seed_spin_ctrl"),
		("top_k_visible", "top_k_label", "top_k_spin_ctrl"),
		("stop_visible", "stop_label", "stop_text_ctrl"),
	)

	def _apply_output_visibility(self, state: ParameterVisibilityState) -> None:
		"""Apply output group visibility.

		Hides the group when no model is selected. Temperature, top_p, and
		advanced params are hidden unless advanced mode is on.
		"""
		if hasattr(self, "output_group_box"):
			self.output_group_box.Show(state.stream_visible)
		if hasattr(self, "output_group_panel"):
			self.output_group_panel.Show(state.stream_visible)
		for state_attr, label_attr, ctrl_attr in self._OUTPUT_VISIBILITY:
			visible = getattr(state, state_attr)
			for attr in (label_attr, ctrl_attr):
				ctrl = getattr(self, attr, None)
				if ctrl is not None:
					ctrl.Enable(visible)
					ctrl.Show(visible)
		self.stream_mode.Enable(state.stream_visible)
		self.stream_mode.Show(state.stream_visible)

	def _apply_audio_visibility(self, state: ParameterVisibilityState) -> None:
		"""Apply audio output group visibility."""
		if hasattr(self, "audio_output_group_box"):
			visible = state.output_modality_visible
			self.audio_output_group_box.Show(visible)
			for ctrl in (
				self.output_modality_label,
				self.output_modality_choice,
			):
				ctrl.Enable(visible)
				ctrl.Show(visible)
			for ctrl in (self.audio_voice_label, self.audio_voice_choice):
				ctrl.Enable(visible and state.audio_settings_visible)
				ctrl.Show(visible and state.audio_settings_visible)

	def _apply_tools_visibility(self, state: ParameterVisibilityState) -> None:
		"""Apply tools group visibility state.

		Tools group (web search, etc.) is hidden when no tools are available.
		"""
		if hasattr(self, "tools_group_box"):
			self.tools_group_box.Show(state.web_search_visible)
		if hasattr(self, "web_search_mode"):
			self.web_search_mode.Enable(state.web_search_visible)
			self.web_search_mode.Show(state.web_search_visible)

	def _apply_reasoning_visibility(
		self, state: ParameterVisibilityState
	) -> None:
		"""Apply reasoning group visibility.

		Reasoning controls are hidden when model does not support them.
		"""
		if hasattr(self, "reasoning_group_box"):
			self.reasoning_group_box.Show(state.reasoning_mode_visible)
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
