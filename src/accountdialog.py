import wx
from config import conf
from localization import _
from logging import getLogger
from account import (
	Account,
	accountManager,
	AccountSource,
	ACCOUNT_SOURCE_LABELS,
)
from config import save_accounts
from provider import providers, Provider, get_provider

log = getLogger(__name__)


class EditAccountDialog(wx.Dialog):
	def __init__(self, parent, title, size=(400, 400), account: Account = None):
		wx.Dialog.__init__(self, parent, title=title, size=size)
		self.parent = parent
		self.account = account
		self.initUI()
		if account:
			self.init_data()
			self.update_ui()
		self.Centre()
		self.Show()
		self.name.SetFocus()

	def initUI(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)

		label = wx.StaticText(panel, label=_("Name:"), style=wx.ALIGN_LEFT)
		sizer.Add(label, 0, wx.ALL, 5)
		self.name = wx.TextCtrl(panel)
		sizer.Add(self.name, 0, wx.EXPAND)

		label = wx.StaticText(panel, label=_("Provider:"), style=wx.ALIGN_LEFT)
		sizer.Add(label, 0, wx.ALL, 5)
		choices = [provider.name for provider in providers]
		self.provider = wx.ComboBox(
			panel, choices=choices, style=wx.CB_READONLY
		)
		self.provider.Bind(wx.EVT_COMBOBOX, lambda e: self.update_ui())
		sizer.Add(self.provider, 0, wx.EXPAND)

		label = wx.StaticText(panel, label=_("API key:"), style=wx.ALIGN_LEFT)
		sizer.Add(label, 0, wx.ALL, 5)
		self.api_key = wx.TextCtrl(panel)
		self.api_key.Disable()
		sizer.Add(self.api_key, 0, wx.EXPAND)

		self.use_organization_key = wx.CheckBox(
			panel, label=_("Use organization key")
		)
		self.use_organization_key.Bind(
			wx.EVT_CHECKBOX, lambda e: self.update_ui()
		)
		self.use_organization_key.Disable()
		sizer.Add(self.use_organization_key, 0, wx.EXPAND)

		label = wx.StaticText(
			panel, label=_("Organization key"), style=wx.ALIGN_LEFT
		)
		sizer.Add(label, 0, wx.ALL, 5)
		self.organization_key = wx.TextCtrl(panel)
		self.organization_key.Disable()
		sizer.Add(self.organization_key, 0, wx.EXPAND)

		bSizer = wx.BoxSizer(wx.HORIZONTAL)

		btn = wx.Button(panel, wx.ID_OK, _("Save"))
		btn.SetDefault()
		btn.Bind(wx.EVT_BUTTON, self.on_ok)
		bSizer.Add(btn, 0, wx.ALL, 5)

		btn = wx.Button(panel, wx.ID_CANCEL, _("Cancel"))
		btn.Bind(wx.EVT_BUTTON, self.on_cancel)
		bSizer.Add(btn, 0, wx.ALL, 5)

		sizer.Add(bSizer, 0, wx.ALL, 5)

	def init_data(self):
		if self.account:
			self.name.SetValue(self.account.name)
			index = -1
			for i, provider in enumerate(providers):
				if provider.name == self.account.provider.name:
					index = i
					break
			self.provider.SetSelection(index)
			if self.account.api_key:
				self.api_key.SetValue(self.account.api_key)
			if self.account.provider.organization_mode_available:
				if self.account.organization_key:
					self.organization_key.SetValue(
						self.account.organization_key
					)
				self.use_organization_key.SetValue(
					self.account.use_organization_key
				)

	def update_ui(self):
		provider_index = self.provider.GetSelection()
		if provider_index == -1:
			log.debug("No provider selected")
			return
		provider_name = self.provider.GetValue()
		provider = get_provider(provider_name)
		if not provider:
			log.debug("Provider not found")
			return
		self.api_key.Enable(provider.require_api_key)
		self.use_organization_key.Enable(provider.organization_mode_available)
		self.organization_key.Enable(
			provider.organization_mode_available
			and self.use_organization_key.GetValue()
		)

	def on_ok(self, event):
		if not self.name.GetValue():
			msg = _("Please enter a name")
			wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
			self.name.SetFocus()
			return
		provider_index = self.provider.GetSelection()
		if provider_index == -1:
			msg = _("Please select a provider")
			wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
			self.provider.SetFocus()
			return
		provider_name = self.provider.GetValue()
		provider = get_provider(provider_name)
		if not provider:
			msg = _("Provider not found")
			wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
			return
		if provider.require_api_key and not self.api_key.GetValue():
			msg = _("Please enter an API key. It is required for this provider")
			wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
			self.api_key.SetFocus()
			return
		self.account = Account(
			name=self.name.GetValue(),
			provider=provider,
			api_key=self.api_key.GetValue(),
			organization_key=self.organization_key.GetValue(),
			use_organization_key=self.use_organization_key.GetValue(),
			source=AccountSource.CONFIG,
		)
		self.EndModal(wx.ID_OK)

	def on_cancel(self, event):
		self.EndModal(wx.ID_CANCEL)


class AccountDialog(wx.Dialog):
	"""Manage account settings"""

	def __init__(self, parent, title, size=(400, 400)):
		wx.Dialog.__init__(self, parent, title=title, size=size)
		self.parent = parent
		self.init_ui()
		self.init_data()
		self.update_data()
		self.Centre()
		self.Show()

	def init_ui(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)

		label = wx.StaticText(panel, label=_("Accounts"), style=wx.ALIGN_LEFT)
		sizer.Add(label, 0, wx.ALL, 5)
		self.account_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
		self.account_list.InsertColumn(0, _("Name"))
		self.account_list.InsertColumn(1, _("Provider"))
		self.account_list.InsertColumn(2, _("Use organization key"))
		self.account_list.InsertColumn(3, _("Source"))
		self.account_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_item_selected)
		sizer.Add(self.account_list, 1, wx.EXPAND)

		add_btn = wx.Button(panel, label=_("&Add"))
		sizer.Add(add_btn, 0, wx.ALL, 5)
		self.edit_btn = wx.Button(panel, label=_("&Edit"))
		self.edit_btn.Disable()
		sizer.Add(self.edit_btn, 0, wx.ALL, 5)
		self.remove_btn = wx.Button(panel, label=_("&Remove"))
		self.remove_btn.Disable()
		sizer.Add(self.remove_btn, 0, wx.ALL, 5)

		self.Bind(wx.EVT_BUTTON, self.on_add, add_btn)
		self.Bind(wx.EVT_BUTTON, self.on_edit, self.edit_btn)
		self.Bind(wx.EVT_BUTTON, self.on_remove, self.remove_btn)

		bSizer = wx.BoxSizer(wx.HORIZONTAL)

		btn = wx.Button(panel, wx.ID_OK, _("Save"))
		btn.Bind(wx.EVT_BUTTON, self.onOK)
		bSizer.Add(btn, 0, wx.ALL, 5)

		btn = wx.Button(panel, wx.ID_CANCEL, _("Cancel"))
		btn.Bind(wx.EVT_BUTTON, self.onCancel)
		bSizer.Add(btn, 0, wx.ALL, 5)

		sizer.Add(bSizer, 0, wx.ALL, 5)

	def init_data(self):
		self.accountManager = accountManager.copy()

	def update_data(self):
		for account in self.accountManager:
			self.account_list.Append(
				(
					account.name,
					account.provider.name,
					_("Yes") if account.use_organization_key else _("No"),
					ACCOUNT_SOURCE_LABELS.get(account.source, _("Unknown")),
				)
			)

	def on_item_selected(self, event):
		account = self.accountManager[self.account_list.GetFirstSelected()]
		editable = account.source != AccountSource.ENV_VAR
		self.edit_btn.Enable(editable)
		self.remove_btn.Enable(editable)

	def on_add(self, event):
		dialog = EditAccountDialog(self, _("Add account"))
		if dialog.ShowModal() == wx.ID_OK:
			account = dialog.account
			self.accountManager.add(account)
			self.account_list.Append(
				(
					account.name,
					account.provider.name,
					_("Yes") if account.use_organization_key else _("No"),
					ACCOUNT_SOURCE_LABELS.get(account.source, _("Unknown")),
				)
			)
		dialog.Destroy()
		self.account_list.SetItemState(
			self.account_list.GetItemCount() - 1,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
		)

	def on_edit(self, event):
		index = self.account_list.GetFirstSelected()
		if index == -1:
			return
		account = self.accountManager[index]
		if account.source == AccountSource.ENV_VAR:
			msg = _("Cannot edit account from environment variable")
			wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
			return
		dialog = EditAccountDialog(self, _("Edit account"), account=account)
		if dialog.ShowModal() == wx.ID_OK:
			account = dialog.account
			self.accountManager[index] = account
			self.account_list.SetStringItem(index, 0, account.name)
			self.account_list.SetStringItem(index, 1, account.provider.name)
			self.account_list.SetStringItem(
				index, 2, _("Yes") if account.use_organization_key else _("No")
			)
			self.account_list.SetStringItem(
				index,
				3,
				ACCOUNT_SOURCE_LABELS.get(account.source, _("Unknown")),
			)
		dialog.Destroy()
		self.account_list.SetItemState(
			index,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
		)

	def on_remove(self, event):
		index = self.account_list.GetFirstSelected()
		if index == -1:
			return
		account = self.accountManager[index]
		if account.source == AccountSource.ENV_VAR:
			msg = _("Cannot remove account from environment variable")
			wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
			return
		self.accountManager.remove(account)
		self.account_list.DeleteItem(index)

	def onOK(self, event):
		accountManager.clear()
		for account in self.accountManager:
			accountManager.add(account)
			save_accounts(accountManager)
		self.EndModal(wx.ID_OK)

	def onCancel(self, event):
		self.EndModal(wx.ID_CANCEL)
