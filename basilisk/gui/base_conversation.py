import wx
from more_itertools import locate
from wx.lib.agw.floatspin import FloatSpin

import basilisk.config as config


class FloatSpinTextCtrlAccessible(wx.Accessible):
	def __init__(self, win: wx.Window = None, name: str = None):
		super().__init__(win)
		self._name = name

	def GetName(self, childId):
		if self._name:
			return (wx.ACC_OK, self._name)
		return super().GetName(childId)


class BaseConversation:
	def create_account_widget(self) -> wx.StaticText:
		label = wx.StaticText(
			self,
			# Translators: This is a label for account in the main window
			label=_("&Account:"),
		)
		self.account_combo = wx.ComboBox(
			self, style=wx.CB_READONLY, choices=self.get_display_accounts()
		)
		if len(self.account_combo.GetItems()) > 0:
			self.select_default_account()
		return label

	def select_default_account(self):
		accounts = config.accounts()
		account_index = next(
			locate(accounts, lambda a: a == accounts.default_account),
			wx.NOT_FOUND,
		)
		if account_index != wx.NOT_FOUND:
			self.account_combo.SetSelection(account_index)

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
		self.model_list.InsertColumn(0, _("Name"))
		self.model_list.InsertColumn(1, _("Context window"))
		self.model_list.InsertColumn(2, _("Max tokens"))
		self.model_list.SetColumnWidth(0, 200)
		self.model_list.SetColumnWidth(1, 100)

		return label

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
