"""Account dialog for managing accounts and organizations in the basiliskLLM application."""

import logging
from typing import Optional

import wx
from more_itertools import first, locate
from pydantic import SecretStr

from basilisk.config import (
	Account,
	AccountOrganization,
	AccountSource,
	KeyStorageMethodEnum,
	accounts,
)
from basilisk.provider import Provider, get_provider, providers

log = logging.getLogger(__name__)

key_storage_methods = KeyStorageMethodEnum.get_labels()


class EditAccountOrganizationDialog(wx.Dialog):
	"""Dialog for editing account organization settings in the basiliskLLM application."""

	def __init__(
		self,
		parent: wx.Window,
		title: str,
		organization: Optional[AccountOrganization] = None,
		size: tuple[int, int] = (400, 200),
	):
		"""Initialize the dialog for editing account organization settings.

		Args:
			parent: The parent window.
			title: The title of the dialog.
			organization: The organization to edit. If None, a new organization will be created.
			size: The size of the dialog.
		"""
		wx.Dialog.__init__(self, parent, title=title, size=size)
		self.parent = parent
		self.organization = organization
		self.init_ui()
		self.init_data()
		self.update_data()
		self.Centre()
		self.Show()
		self.name.SetFocus()

	def init_ui(self):
		"""Initialize the user interface of the dialog.

		The dialog contains fields for entering the organization name, key storage method, and key.
		"""
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)

		label = wx.StaticText(
			panel,
			# Translators: A label in account dialog
			label=_("&Name:"),
			style=wx.ALIGN_LEFT,
		)
		sizer.Add(label, 0, wx.ALL, 5)
		self.name = wx.TextCtrl(panel)
		sizer.Add(self.name, 0, wx.EXPAND)

		label = wx.StaticText(
			panel,
			# Translators: A label in account dialog
			label=_("Organisation key storage &method:"),
			style=wx.ALIGN_LEFT,
		)
		sizer.Add(label, 0, wx.ALL, 5)
		self.key_storage_method = wx.ComboBox(
			panel,
			choices=list(key_storage_methods.values()),
			style=wx.CB_READONLY,
		)
		sizer.Add(self.key_storage_method, 0, wx.EXPAND)
		label = wx.StaticText(
			panel,
			# Translators: A label in account dialog
			label=_("Organisation &Key:"),
			style=wx.ALIGN_LEFT,
		)
		sizer.Add(label, 0, wx.ALL, 5)
		self.key = wx.TextCtrl(panel)
		sizer.Add(self.key, 0, wx.EXPAND)

		bSizer = wx.BoxSizer(wx.HORIZONTAL)

		btn = wx.Button(panel, wx.ID_OK)
		btn.SetDefault()
		btn.Bind(wx.EVT_BUTTON, self.on_ok)
		bSizer.Add(btn, 0, wx.ALL, 5)

		btn = wx.Button(panel, wx.ID_CANCEL)
		btn.Bind(wx.EVT_BUTTON, self.on_cancel)
		bSizer.Add(btn, 0, wx.ALL, 5)

		sizer.Add(bSizer, 0, wx.ALL, 5)

	def init_data(self):
		"""Initialize the data for the dialog.

		If an organization is provided, the organization's name, key storage method, and key are set in the dialog.
		"""
		if not self.organization:
			self.key_storage_method.SetSelection(0)
			return

		self.name.SetValue(self.organization.name)
		index = first(
			locate(
				key_storage_methods.keys(),
				lambda x: x == self.organization.key_storage_method,
			),
			-1,
		)
		self.key_storage_method.SetSelection(index)
		self.key.SetValue(self.organization.key.get_secret_value())

	def update_data(self):
		"""Update the data in the dialog."""
		pass

	def on_ok(self, event: wx.Event | None):
		"""Handle the OK button click event.

		Validate the organization name, key storage method, and key. If the organization is valid, set the organization data and close the dialog.
		"""
		if not self.name.GetValue():
			msg = _("Please enter a name")
			wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
			self.name.SetFocus()
			return
		if self.key_storage_method.GetSelection() == -1:
			msg = _("Please select a key storage method")
			wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
			self.key_storage_method.SetFocus()
			return
		if not self.key.GetValue():
			msg = _("Please enter a key")
			wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
			self.key.SetFocus()
			return
		key_storage_method = list(key_storage_methods.keys())[
			self.key_storage_method.GetSelection()
		]
		if self.organization:
			self.organization.name = self.name.GetValue()
			self.organization.key_storage_method = key_storage_method
			self.organization.key = SecretStr(self.key.GetValue())
		else:
			self.organization = AccountOrganization(
				name=self.name.GetValue(),
				key_storage_method=key_storage_method,
				key=SecretStr(self.key.GetValue()),
			)
		self.EndModal(wx.ID_OK)

	def on_cancel(self, event: wx.Event | None):
		"""Handle the Cancel button click event.

		Close the dialog without saving any changes.
		"""
		self.EndModal(wx.ID_CANCEL)


class AccountOrganizationDialog(wx.Dialog):
	"""Dialog for managing account organizations in the basiliskLLM application."""

	def __init__(
		self,
		parent: wx.Window,
		title: str,
		account: Account,
		size: tuple[int, int] = (400, 400),
	):
		"""Initialize the dialog for managing account organizations.

		Args:
			parent: The parent window.
			title: The title of the dialog.
			account: The account to manage organizations for.
			size: The size of the dialog.
		"""
		wx.Dialog.__init__(self, parent, title=title, size=size)
		self.account_source_labels = AccountSource.get_labels()
		self.parent = parent
		self.account = account
		self.init_ui()
		self.init_data()
		self.update_data()
		self.Centre()
		self.Show()

	def init_ui(self):
		"""Initialize the user interface of the dialog.

		The dialog contains a list of organizations, and buttons for adding, editing, and removing organizations.
		"""
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)

		label = wx.StaticText(
			panel, label=_("Organizations"), style=wx.ALIGN_LEFT
		)
		sizer.Add(label, 0, wx.ALL, 5)
		self.organization_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
		self.organization_list.InsertColumn(
			0,
			# Translators: A label in account dialog
			_("Name"),
		)
		self.organization_list.InsertColumn(
			1,
			# Translators: A label in account dialog
			_("Key"),
		)
		self.organization_list.InsertColumn(
			2,
			# Translators: A label in account dialog
			_("Source"),
		)
		self.organization_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.update_ui)
		self.organization_list.Bind(wx.EVT_KEY_DOWN, self.on_org_list_key_down)
		sizer.Add(self.organization_list, 1, wx.EXPAND)

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

		btn = wx.Button(panel, wx.ID_OK)
		btn.Bind(wx.EVT_BUTTON, self.on_ok)
		bSizer.Add(btn, 0, wx.ALL, 5)

		btn = wx.Button(panel, wx.ID_CANCEL)
		btn.Bind(wx.EVT_BUTTON, self.on_cancel)
		bSizer.Add(btn, 0, wx.ALL, 5)

		sizer.Add(bSizer, 0, wx.ALL, 5)

	def init_data(self):
		"""Initialize the data for the dialog.

		The organizations for the account are set in the dialog.
		"""
		self.organizations = self.account.organizations or []

	def update_data(self):
		"""Update the data in the dialog.

		Add the organisations data to the list control.
		"""
		for organization in self.organizations:
			self.organization_list.Append(
				(
					organization.name,
					organization.key.get_secret_value(),
					self.account_source_labels.get(
						organization.source, _("Unknown")
					),
				)
			)

	def update_ui(self, event: wx.Event | None):
		"""Update the user interface of the dialog.

		Enable or disable the edit and remove buttons based on the selected organization.

		Args:
			event: The event that triggered the update. If None, the update was not triggered by an event.
		"""
		selected_item = self.organization_list.GetFirstSelected()
		if selected_item == -1:
			self.edit_btn.Disable()
			self.remove_btn.Disable()
			return
		organization = self.organizations[selected_item]
		if organization.source == AccountSource.ENV_VAR:
			self.edit_btn.Disable()
			self.remove_btn.Disable()
			return
		self.edit_btn.Enable()
		self.remove_btn.Enable()

	def on_add(self, event: wx.Event | None):
		"""Handle the Add button click event.

		Open the EditAccountOrganizationDialog to add a new organization to the account.
		"""
		dialog = EditAccountOrganizationDialog(self, _("Add organization"))
		if dialog.ShowModal() == wx.ID_OK:
			organization = dialog.organization
			self.organizations.append(organization)
			self.organization_list.Append(
				(
					organization.name,
					organization.key.get_secret_value(),
					self.account_source_labels.get(
						organization.source, _("Unknown")
					),
				)
			)
		dialog.Destroy()
		self.organization_list.SetItemState(
			self.organization_list.GetItemCount() - 1,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
		)
		self.organization_list.EnsureVisible(
			self.organization_list.GetItemCount() - 1
		)

	def on_edit(self, event: wx.Event | None):
		"""Handle the Edit button click event.

		Open the EditAccountOrganizationDialog to edit the selected organization.
		"""
		selected_item = self.organization_list.GetFirstSelected()
		organization = self.organizations[selected_item]
		dialog = EditAccountOrganizationDialog(
			self, _("Edit organization"), organization
		)
		if dialog.ShowModal() == wx.ID_OK:
			organization = dialog.organization
			self.organizations[selected_item] = organization
			self.organization_list.SetItem(selected_item, 0, organization.name)
			self.organization_list.SetItem(
				selected_item, 1, organization.key.get_secret_value()
			)
			self.organization_list.SetItem(
				selected_item,
				2,
				self.account_source_labels.get(
					organization.source, _("Unknown")
				),
			)
		dialog.Destroy()
		self.organization_list.SetItemState(
			selected_item,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
		)
		self.organization_list.EnsureVisible(selected_item)

	def on_remove(self, event: wx.Event | None):
		"""Handle the Remove button click event.

		Remove the selected organization from the account.
		"""
		index = self.organization_list.GetFirstSelected()
		organization = self.organizations[index]
		# Translators: A confirmation message in account dialog for removing organization
		msg = _("Are you sure you want to remove the organization {}?").format(
			organization.name
		)
		if wx.MessageBox(msg, _("Confirmation"), wx.YES_NO) != wx.YES:
			return
		organization.delete_keyring_password()
		self.organization_list.Select(index - 1)
		self.organization_list.DeleteItem(index)
		if self.account.active_organization_id == organization.id:
			self.account.active_organization_id = None
		self.organizations.pop(index)
		self.update_ui()

	def on_ok(self, event: wx.Event | None):
		"""Handle the OK button click event.

		Save the organizations to the account and close the dialog.
		"""
		self.account.organizations = self.organizations
		self.EndModal(wx.ID_OK)

	def on_cancel(self, event: wx.Event | None):
		"""Handle the Cancel button click event.

		Close the dialog without saving any changes.
		"""
		self.EndModal(wx.ID_CANCEL)

	def on_org_list_key_down(self, event: wx.KeyEvent):
		"""Handle the key down event on the organization list.

		Handle the Enter and Delete keys to edit and remove organizations.
		"""
		if event.GetKeyCode() == wx.WXK_RETURN:
			self.on_edit(event)
		elif event.GetKeyCode() == wx.WXK_DELETE:
			self.on_remove(event)
		else:
			event.Skip()


class EditAccountDialog(wx.Dialog):
	"""Dialog for editing or creating accounts in the basiliskLLM application."""

	def __init__(
		self,
		parent: wx.Window,
		title: str,
		size: tuple[int, int] = (400, 400),
		account: Account | None = None,
	):
		"""Initialize the dialog for editing account settings.

		Args:
			parent: The parent window.
			title: The title of the dialog.
			size: The size of the dialog.
			account: The account to edit. If None, a new account will be created.
		"""
		super().__init__(parent, title=title, size=size)
		self.parent = parent
		self.account = account
		self.init_ui()
		if account:
			self.init_data()
		self.update_ui()
		self.Centre()
		self.Show()
		self.name.SetFocus()

	def init_ui(self):
		"""Initialize the user interface of the dialog.

		The dialog contains fields for entering the account name, provider,
		API key storage method, API key, and organization selection.
		"""
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)

		label = wx.StaticText(
			panel,
			# Translators: A label in account dialog
			label=_("&Name:"),
			style=wx.ALIGN_LEFT,
		)
		sizer.Add(label, 0, wx.ALL, 5)
		self.name = wx.TextCtrl(panel)
		sizer.Add(self.name, 0, wx.EXPAND)

		self.provider_label = wx.StaticText(
			panel,
			# Translators: A label in account dialog
			label=_("&Provider:"),
			style=wx.ALIGN_LEFT,
		)
		sizer.Add(self.provider_label, 0, wx.ALL, 5)
		provider_choices = [provider.name for provider in providers]
		self.provider_combo = wx.ComboBox(
			panel, choices=provider_choices, style=wx.CB_READONLY
		)
		self.provider_combo.Bind(wx.EVT_COMBOBOX, lambda e: self.update_ui())
		sizer.Add(self.provider_combo, 0, wx.EXPAND)

		self.api_key_storage_method_label = wx.StaticText(
			panel,
			style=wx.ALIGN_LEFT,
			# Translators: A label in account dialog
			label=_("API &key storage method:"),
		)
		sizer.Add(self.api_key_storage_method_label, 0, wx.ALL, 5)
		self.api_key_storage_method_combo = wx.ComboBox(
			panel,
			choices=list(key_storage_methods.values()),
			style=wx.CB_READONLY,
		)
		sizer.Add(self.api_key_storage_method_combo, 0, wx.EXPAND)

		self.api_key_label = wx.StaticText(
			panel,
			style=wx.ALIGN_LEFT,
			# Translators: A label in account dialog
			label=_("API &key:"),
		)
		sizer.Add(self.api_key_label, 0, wx.ALL, 5)
		self.api_key_text_ctrl = wx.TextCtrl(panel)
		sizer.Add(self.api_key_text_ctrl, 0, wx.EXPAND)

		self.organization_label = wx.StaticText(
			panel,
			# Translators: A label in account dialog
			label=_("&Organization to use:"),
			style=wx.ALIGN_LEFT,
		)
		sizer.Add(self.organization_label, 0, wx.ALL, 5)
		self.organization_text_ctrl = wx.ComboBox(panel, style=wx.CB_READONLY)
		sizer.Add(self.organization_text_ctrl, 0, wx.EXPAND)

		self.custom_base_url_label = wx.StaticText(
			panel,
			# Translators: A label in account dialog
			label=_("Custom &base URL:"),
			style=wx.ALIGN_LEFT,
		)
		sizer.Add(self.custom_base_url_label, 0, wx.ALL, 5)
		self.custom_base_url_text_ctrl = wx.TextCtrl(panel)
		sizer.Add(self.custom_base_url_text_ctrl, 0, wx.EXPAND)

		buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

		btn = wx.Button(panel, wx.ID_OK)
		btn.SetDefault()
		btn.Bind(wx.EVT_BUTTON, self.on_ok)
		buttons_sizer.Add(btn, 0, wx.ALL, 5)

		btn = wx.Button(panel, wx.ID_CANCEL)
		btn.Bind(wx.EVT_BUTTON, self.on_cancel)
		buttons_sizer.Add(btn, 0, wx.ALL, 5)

		sizer.Add(buttons_sizer, 0, wx.ALL, 5)

	def init_data(self):
		"""Initialize the data for the dialog.

		If an account is provided, the account's name, provider, API key,
		and organization settings are set in the dialog.
		"""
		if not self.account:
			self.api_key_storage_method_combo.SetSelection(0)
			return

		self.name.SetValue(self.account.name)
		index = first(
			locate(providers, lambda x: x.name == self.account.provider.name),
			-1,
		)
		self.provider_combo.SetSelection(index)

		if self.account.api_key and self.account.api_key_storage_method:
			self._set_api_key_data()

		self._init_organization_data()

		if self.account.custom_base_url:
			self.custom_base_url_text_ctrl.SetValue(
				self.account.custom_base_url
			)

	def _set_api_key_data(self) -> None:
		"""Set API key related fields from account data."""
		index = first(
			locate(
				key_storage_methods.keys(),
				lambda x: x == self.account.api_key_storage_method,
			),
			-1,
		)
		self.api_key_storage_method_combo.SetSelection(index)
		self.api_key_text_ctrl.SetValue(self.account.api_key.get_secret_value())

	def _init_organization_data(self) -> None:
		"""Initialize organization related fields."""
		self.organization_text_ctrl.Enable(
			self.account.provider.organization_mode_available
		)
		if not self.account.provider.organization_mode_available:
			return

		if self.account.organizations:
			choices = [_("Personal")] + [
				organization.name for organization in self.account.organizations
			]
			self.organization_text_ctrl.SetItems(choices)

		if self.account.active_organization_id:
			index = (
				first(
					locate(
						self.account.organizations,
						lambda x: x.id == self.account.active_organization_id,
					),
					-1,
				)
				+ 1
			)
			self.organization_text_ctrl.SetSelection(index)

	def get_selected_provider(self) -> Optional[Provider]:
		"""Get the provider object from the selected provider name.

		Returns:
			The provider object if a provider is selected, otherwise None.
		"""
		provider_index = self.provider_combo.GetSelection()
		if provider_index == wx.NOT_FOUND:
			return None
		provider_name = self.provider_combo.GetValue()
		return get_provider(name=provider_name)

	def update_ui(self) -> None:
		"""Update UI elements based on selected provider."""
		provider = self.get_selected_provider()
		if not provider:
			self._disable_all_fields()
			return

		self._update_api_key_fields(provider.require_api_key)
		self._update_organization_fields(provider.organization_mode_available)
		self._update_base_url_fields(provider)

	def _disable_all_fields(self) -> None:
		"""Disable all provider-dependent fields."""
		fields = [
			self.api_key_label,
			self.api_key_text_ctrl,
			self.api_key_storage_method_label,
			self.api_key_storage_method_combo,
			self.organization_label,
			self.organization_text_ctrl,
			self.custom_base_url_label,
			self.custom_base_url_text_ctrl,
		]
		for field in fields:
			field.Disable()

	def _update_api_key_fields(self, enable: bool) -> None:
		"""Update API key related fields state."""
		fields = [
			self.api_key_label,
			self.api_key_text_ctrl,
			self.api_key_storage_method_label,
			self.api_key_storage_method_combo,
		]
		for field in fields:
			field.Enable(enable)

	def _update_organization_fields(self, enable: bool) -> None:
		"""Update organization related fields state."""
		self.organization_label.Enable(enable)
		self.organization_text_ctrl.Enable(enable)

	def _update_base_url_fields(self, provider: Provider) -> None:
		"""Update base URL related fields."""
		self.custom_base_url_label.Enable(provider.allow_custom_base_url)
		self.custom_base_url_text_ctrl.Enable(provider.allow_custom_base_url)

	def on_ok(self, event: wx.CommandEvent) -> None:
		"""Handle the OK button click event.

		Validate the account settings and create or update the account.
		Close the dialog if all validations pass.

		Args:
			event: The event that triggered the OK button click. If None, the OK button was not clicked.
		"""
		error_message = self._validate_form()
		if error_message:
			wx.MessageBox(
				error_message,
				# Translators: A title for the error message in account dialog
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return

		self._save_account_data()
		self.EndModal(wx.ID_OK)

	def _validate_form(self) -> Optional[str]:
		"""Validate form data and return error message if invalid."""
		if not self.name.GetValue():
			# Translators: An error message in account dialog
			return _("Please enter a name")

		provider = self.get_selected_provider()
		if not provider:
			# Translators: An error message in account dialog
			return _("Please select a provider")

		if provider.require_api_key:
			if self.api_key_storage_method_combo.GetSelection() == wx.NOT_FOUND:
				# Translators: An error message in account dialog
				return _("Please select an API key storage method")
			if not self.api_key_text_ctrl.GetValue():
				# Translators: An error message in account dialog
				return _(
					"Please enter an API key. It is required for this provider"
				)

		return None

	def _save_account_data(self) -> None:
		"""Save form data to account object."""
		provider = self.get_selected_provider()
		organization_index = self.organization_text_ctrl.GetSelection()
		active_organization = None
		if (
			organization_index > 0
			and self.account
			and self.account.organizations
		):
			active_organization = self.account.organizations[
				organization_index - 1
			].id

		api_key_storage_method = None
		api_key = None
		if provider.require_api_key:
			api_key_storage_method = list(key_storage_methods.keys())[
				self.api_key_storage_method_combo.GetSelection()
			]
			api_key = SecretStr(self.api_key_text_ctrl.GetValue())

		custom_base_url = self.custom_base_url_text_ctrl.GetValue()
		if not provider.allow_custom_base_url or not custom_base_url.strip():
			custom_base_url = None

		if self.account:
			self._update_existing_account(
				provider,
				active_organization,
				api_key_storage_method,
				api_key,
				custom_base_url,
			)
		else:
			self._create_new_account(
				provider,
				active_organization,
				api_key_storage_method,
				api_key,
				custom_base_url,
			)

	def _update_existing_account(
		self,
		provider: Provider,
		active_organization: Optional[str],
		api_key_storage_method: Optional[KeyStorageMethodEnum],
		api_key: Optional[SecretStr],
		custom_base_url: Optional[str],
	) -> None:
		"""Update existing account with form data."""
		self.account.name = self.name.GetValue()
		self.account.provider = provider
		self.account.api_key_storage_method = api_key_storage_method
		self.account.api_key = api_key
		self.account.active_organization_id = active_organization
		self.account.custom_base_url = custom_base_url

	def _create_new_account(
		self,
		provider: Provider,
		active_organization: Optional[str],
		api_key_storage_method: Optional[KeyStorageMethodEnum],
		api_key: Optional[SecretStr],
		custom_base_url: Optional[str],
	) -> None:
		"""Create new account from form data."""
		self.account = Account(
			name=self.name.GetValue(),
			provider=provider,
			api_key_storage_method=api_key_storage_method,
			api_key=api_key,
			active_organization_id=active_organization,
			source=AccountSource.CONFIG,
			custom_base_url=custom_base_url,
		)

	def on_cancel(self, event: wx.CommandEvent) -> None:
		"""Handle the Cancel button click event.

		Close the dialog without saving any changes.

		Args:
			event: The event that triggered the Cancel button click. If None, the Cancel button was not clicked.
		"""
		self.EndModal(wx.ID_CANCEL)


class AccountDialog(wx.Dialog):
	"""Manage accounts in the basiliskLLM application."""

	def __init__(
		self, parent: wx.Window, title: str, size: tuple[int, int] = (400, 400)
	):
		"""Initialize the dialog for managing accounts.

		Args:
			parent: The parent window.
			title: The title of the dialog.
			size: The size of the dialog.
		"""
		wx.Dialog.__init__(self, parent, title=title, size=size)
		self.account_source_labels = AccountSource.get_labels()
		self.parent = parent
		self.init_ui()
		self.init_data()
		self.update_data()
		self.Centre()
		self.Show()

	def init_ui(self):
		"""Initialize the user interface of the dialog.

		The dialog contains a list of accounts, buttons for adding, editing, removing accounts,
		managing organizations, and setting the default account.
		"""
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)

		label = wx.StaticText(
			panel,
			# Translators: A label in account dialog
			label=_("Accounts"),
			style=wx.ALIGN_LEFT,
		)
		sizer.Add(label, 0, wx.ALL, 5)
		self.account_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
		self.account_list.AppendColumn(
			# Translators: A label in account dialog
			_("Name")
		)
		self.account_list.AppendColumn(
			# Translators: A label in account dialog
			_("Provider")
		)
		self.account_list.AppendColumn(
			# Translators: A label in account dialog
			_("Active organization")
		)
		self.account_list.AppendColumn(
			# Translators: A label in account dialog
			_("Source")
		)
		self.account_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.update_ui)
		self.account_list.Bind(wx.EVT_KEY_DOWN, self.on_account_list_key_down)
		sizer.Add(self.account_list, 1, wx.EXPAND)

		add_btn = wx.Button(panel, label=_("&Add"))
		sizer.Add(add_btn, 0, wx.ALL, 5)

		self.manage_organizations = wx.Button(
			panel, label=_("&Manage organizations...")
		)
		self.manage_organizations.Disable()
		sizer.Add(self.manage_organizations, 0, wx.ALL, 5)

		self.edit_btn = wx.Button(panel, label=_("&Edit"))
		self.edit_btn.Disable()
		sizer.Add(self.edit_btn, 0, wx.ALL, 5)

		self.remove_btn = wx.Button(panel, label=_("&Remove"))
		self.remove_btn.Disable()
		sizer.Add(self.remove_btn, 0, wx.ALL, 5)

		self.default_account_btn = wx.ToggleButton(
			panel, label=_("Default account")
		)
		self.default_account_btn.Disable()
		sizer.Add(self.default_account_btn, 0, wx.ALL, 5)
		self.Bind(
			wx.EVT_BUTTON,
			self.on_manage_organizations,
			self.manage_organizations,
		)
		self.Bind(wx.EVT_BUTTON, self.on_add, add_btn)
		self.Bind(wx.EVT_BUTTON, self.on_edit, self.edit_btn)
		self.Bind(wx.EVT_BUTTON, self.on_remove, self.remove_btn)
		self.Bind(
			wx.EVT_TOGGLEBUTTON,
			self.on_default_account,
			self.default_account_btn,
		)
		btn = wx.Button(panel, wx.ID_CLOSE)
		btn.Bind(wx.EVT_BUTTON, self.on_close)
		self.SetEscapeId(btn.GetId())
		sizer.Add(btn, 0, wx.ALL, 5)

	def init_data(self):
		"""Initialize the data for the dialog.

		Get the singleton account manager instance.
		"""
		self.account_manager = accounts()

	def _get_organization_name(self, account: Account) -> str:
		"""Get a display name for the active organization of an account.

		Args:
			account: The account to get the organization name for.

		Returns:
			A string containing either the organization name or "No (personal)" if no organization is active.
		"""
		if not account.active_organization:
			return _("No (personal)")
		return account.active_organization.name

	def add_account_to_list_ctrl(self, account: Account):
		"""Add an account to the list control.

		Args:
			account: The account to add to the list control.
		"""
		self.account_list.Append(
			(
				account.name,
				account.provider.name,
				self._get_organization_name(account),
				self.account_source_labels.get(account.source, _("Unknown")),
			)
		)

	def update_data(self):
		"""Update the data shown in the dialog.

		Add all accounts from the account manager to the list control.
		"""
		for account in self.account_manager:
			self.add_account_to_list_ctrl(account)

	def update_ui(self, event: wx.Event | None = None):
		"""Update the user interface elements based on the selected account.

		Enable/disable buttons based on the account source and provider capabilities.
		Update the default account toggle button state.

		Args:
			event: The event that triggered the update. If None, the update was not triggered by an event.
		"""
		account = self.account_manager[self.account_list.GetFirstSelected()]
		log.debug(f"Selected account: {account}")
		editable = account.source != AccountSource.ENV_VAR
		self.edit_btn.Enable(editable)
		self.remove_btn.Enable(editable)
		self.manage_organizations.Enable(
			editable and account.provider.organization_mode_available
		)
		self.default_account_btn.Enable()
		self.default_account_btn.SetValue(
			self.account_manager.default_account == account
		)

	def on_account_list_key_down(self, event: wx.KeyEvent):
		"""Handle the key down event on the account list.

		Handle the Enter and Delete keys to edit and remove accounts.

		Args:
			event: The key down event.
		"""
		if event.GetKeyCode() == wx.WXK_RETURN:
			self.on_edit(event)
		elif event.GetKeyCode() == wx.WXK_DELETE:
			self.on_remove(event)
		else:
			event.Skip()

	def on_manage_organizations(self, event: wx.Event | None):
		"""Handle the Manage organizations button click event.

		Open the AccountOrganizationDialog to manage organizations for the selected account.

		Args:
			event: The event that triggered the Manage organizations button click.
		"""
		index = self.account_list.GetFirstSelected()
		account = self.account_manager[index]
		dialog = AccountOrganizationDialog(
			self, _("Manage organizations"), account.model_copy(deep=True)
		)
		if dialog.ShowModal() == wx.ID_OK:
			dialog.account.reset_active_organization()
			self.account_manager[index] = dialog.account
			self.account_manager.save()
			self.account_list.SetItem(
				index, 2, self._get_organization_name(dialog.account)
			)
		dialog.Destroy()
		self.account_list.SetItemState(
			index,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
		)
		self.account_list.EnsureVisible(index)

	def on_add(self, event: wx.Event | None):
		"""Handle the Add button click event.

		Open the EditAccountDialog to add a new account to the account manager.

		Args:
			event: The event that triggered the Add button click.
		"""
		dialog = EditAccountDialog(self, _("Add account"))
		if dialog.ShowModal() == wx.ID_OK:
			account = dialog.account
			self.account_manager.add(account)
			self.account_manager.save()
			self.add_account_to_list_ctrl(account)
		dialog.Destroy()
		for i in range(self.account_list.GetItemCount()):
			self.account_list.Select(i, False)
		self.account_list.SetItemState(
			self.account_list.GetItemCount() - 1,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
		)
		self.account_list.EnsureVisible(self.account_list.GetItemCount() - 1)
		self.update_ui()

	def on_edit(self, event: wx.Event | None):
		"""Handle the Edit button click event.

		Open the EditAccountDialog to edit the selected account.

		Args:
			event: The event that triggered the Edit button click.
		"""
		index = self.account_list.GetFirstSelected()
		if index == -1:
			return
		account = self.account_manager[index]
		if account.source == AccountSource.ENV_VAR:
			msg = _("Cannot edit account from environment variable")
			wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
			return
		dialog = EditAccountDialog(
			self, _("Edit account"), account=account.model_copy(deep=True)
		)
		if dialog.ShowModal() == wx.ID_OK:
			account = dialog.account
			account.reset_active_organization()
			self.account_manager[index] = account
			self.account_manager.save()
			self.account_list.SetItem(index, 0, account.name)
			self.account_list.SetItem(index, 1, account.provider.name)
			self.account_list.SetItem(
				index, 2, self._get_organization_name(account)
			)
			self.account_list.SetItem(
				index,
				3,
				self.account_source_labels.get(account.source, _("Unknown")),
			)
		dialog.Destroy()
		self.account_list.SetItemState(
			index,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
		)
		self.account_list.EnsureVisible(index)
		self.update_ui()

	def on_remove(self, event: wx.Event | None):
		"""Handle the Remove button click event.

		Remove the selected account from the account manager.

		Args:
			event: The event that triggered the Remove button click.
		"""
		index = self.account_list.GetFirstSelected()
		if index == -1:
			return
		account = self.account_manager[index]
		account_name = account.name
		# Translators: A confirmation message in account dialog
		msg = _("Are you sure you want to remove the account {}?").format(
			account_name
		)
		if wx.MessageBox(msg, _("Confirmation"), wx.YES_NO) != wx.YES:
			return
		if account.source == AccountSource.ENV_VAR:
			msg = _("Cannot remove account from environment variable")
			wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
			return
		self.account_manager.remove(account)
		self.account_manager.save()
		self.account_list.DeleteItem(index)

	def on_default_account(self, event: wx.Event | None):
		"""Handle the default account toggle button click event.

		Set the selected account as the default account.

		Args:
			event: The event that triggered the default account toggle button click.
		"""
		index = self.account_list.GetFirstSelected()
		if index == -1:
			return
		account = self.account_manager[index]
		if self.account_manager.default_account == account:
			return
		if self.default_account_btn.GetValue():
			self.account_manager.set_default_account(account)
		else:
			self.account_manager.set_default_account(None)
		self.account_manager.save()
		self.update_ui()

	def on_close(self, event: wx.Event | None):
		"""Handle the Close button click event.

		Close the dialog.

		Args:
			event: The event that triggered the Close button click.
		"""
		self.EndModal(wx.ID_OK)
