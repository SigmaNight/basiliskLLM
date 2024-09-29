from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

import wx
from more_itertools import locate
from wx.lib.agw.floatspin import FloatSpin

import basilisk.config as config
from basilisk.provider_ai_model import ProviderAIModel

if TYPE_CHECKING:
	from basilisk.provider_engine.base_engine import BaseEngine


class FloatSpinTextCtrlAccessible(wx.Accessible):
	def __init__(self, win: wx.Window = None, name: str = None):
		super().__init__(win)
		self._name = name

	def GetName(self, childId):
		if self._name:
			return (wx.ACC_OK, self._name)
		return super().GetName(childId)


class BaseConversation:
	def __init__(self):
		self.accounts_engines: dict[UUID, BaseEngine] = {}

	@property
	def current_engine(self) -> BaseEngine:
		return self.accounts_engines[self.current_account.id]

	def create_account_widget(self) -> wx.StaticText:
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
		accounts = config.accounts()
		account_index = self.account_combo.GetSelection()
		if account_index == wx.NOT_FOUND:
			return None
		return accounts[account_index]

	def set_account_combo(
		self,
		account: config.Account,
		accounts: config.AccountManager = config.accounts(),
	):
		index = next(locate(accounts, lambda a: a == account), wx.NOT_FOUND)
		if index != wx.NOT_FOUND:
			self.account_combo.SetSelection(index)
			self.on_account_change(None)

	def select_default_account(self):
		if len(self.account_combo.GetItems()) == 0:
			return
		accounts = config.accounts()
		self.set_account_combo(accounts.default_account, accounts)

	def get_display_accounts(self, force_refresh: bool = False) -> list[str]:
		accounts = []
		for account in config.accounts():
			if force_refresh:
				account.reset_active_organization()
			name = account.name
			organization = (
				account.active_organization.name
				if account.active_organization
				else _("Personal")
			)
			provider_name = account.provider.name
			accounts.append(f"{name} ({organization}) - {provider_name}")
		return accounts

	def on_account_change(self, event) -> Optional[config.Account]:
		account = self.current_account
		if not account:
			return None
		self.accounts_engines.setdefault(
			account.id, account.provider.engine_cls(account)
		)
		self.update_model_list()
		return account

	def create_system_prompt_widget(self) -> wx.StaticText:
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
		return label

	def update_model_list(self):
		self.model_list.DeleteAllItems()
		for model in self.get_display_models():
			self.model_list.Append(model)

	def get_display_models(self) -> list[tuple[str, str, str]]:
		return [m.display_model for m in self.current_engine.models]

	def set_model_list(self, model: ProviderAIModel):
		models = self.current_engine.models
		index = next(locate(models, lambda m: m == model), wx.NOT_FOUND)
		if index != wx.NOT_FOUND:
			self.model_list.SetItemState(
				index,
				wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
				wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			)

	@property
	def current_model(self) -> Optional[ProviderAIModel]:
		model_index = self.model_list.GetFirstSelected()
		if model_index == wx.NOT_FOUND:
			return None
		return self.current_engine.models[model_index]

	def set_account_and_model_from_profile(self, profile: config.Profile):
		if not profile.account and not profile.ai_model_info:
			return
		if profile.account:
			self.set_account_combo(profile.account)
		if profile.ai_model_info and not profile.account:
			account = next(
				config.accounts().get_accounts_by_provider(profile.provider),
				None,
			)
			if account:
				self.set_account_combo(account)
		model = self.current_engine.get_model(profile.ai_model_id)
		if model:
			self.set_model_list(model)

	def create_max_tokens_widget(self) -> wx.StaticText:
		label = wx.StaticText(
			self,
			# Translators: This is a label for max tokens in the main window
			label=_("Max to&kens:"),
		)
		self.max_tokens_spin_ctrl = wx.SpinCtrl(
			self, value='0', min=0, max=2000000
		)
		return label

	def create_temperature_widget(self) -> wx.StaticText:
		label = wx.StaticText(
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
			name=label.GetLabel().replace("&", ""),
		)
		self.temperature_spinner._textctrl.SetAccessible(float_spin_accessible)
		return label

	def create_top_p_widget(self) -> wx.StaticText:
		label = wx.StaticText(
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
			name=label.GetLabel().replace("&", ""),
		)
		self.top_p_spinner._textctrl.SetAccessible(float_spin_accessible)
		return label

	def create_stream_widget(self):
		self.stream_mode = wx.CheckBox(
			self,
			# Translators: This is a label for stream mode in the main window
			label=_("&Stream mode"),
		)
		self.stream_mode.SetValue(True)
