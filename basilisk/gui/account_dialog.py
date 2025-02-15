"""Account dialog for managing accounts and organizations in the basiliskLLM application."""

import logging
import re

import wx
from more_itertools import first, locate
from pydantic import SecretStr

from basilisk.config import (
	CUSTOM_BASE_URL_PATTERN,
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
		organization: AccountOrganization | None = None,
		size: tuple[int, int] = (400, 200),
	):
		"""
		Initialize an instance of the Account Organization Editing Dialog.
		
		This constructor creates a dialog window for editing account organization settings.
		If an organization is provided, the dialog is set up to edit the existing organization's data;
		otherwise, it prepares for the creation of a new organization. It initializes the UI components,
		populates necessary data, updates the UI elements, centers the dialog on the screen, displays it,
		and sets the initial focus to the organization name input field.
		
		Parameters:
		    parent (wx.Window): The parent window of the dialog.
		    title (str): The title to be displayed on the dialog.
		    organization (AccountOrganization | None): The organization instance to edit. If None, a new organization is created.
		    size (tuple[int, int]): The size of the dialog window (width, height).
		
		Side Effects:
		    Initializes and displays the dialog, sets focus to the organization name control.
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
		"""
		Initialize an instance of EditAccountDialog for creating or editing an account.
		
		This constructor sets up the dialog window by initializing the user interface elements,
		loading account data when an existing account is provided, and updating the UI based on
		the account's state. The dialog is centered on the screen and the name input field is set
		to receive focus upon display.
		
		Parameters:
		    parent (wx.Window): The parent window for the dialog.
		    title (str): The title displayed on the dialog.
		    size (tuple[int, int], optional): The dimensions (width, height) of the dialog. Defaults to (400, 400).
		    account (Account | None, optional): The account instance to edit. If None, the dialog prepares for creating a new account.
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
		"""
		Initialize the dialog's user interface with input fields and action buttons.
		
		This method sets up the layout and widgets for managing account information. It creates and arranges the following UI components:
		  - A text control for entering the account name.
		  - A read-only combo box for selecting the provider, populated with available provider names. The combo box is bound to update the UI when the selection changes.
		  - A combo box for choosing the API key storage method.
		  - A text control for entering the API key.
		  - A read-only combo box for selecting the organization.
		  - A text control for inputting a custom base URL.
		  - A horizontal sizer containing OK and Cancel buttons for form submission and cancellation.
		
		Uses wxPython controls and sizers for a structured layout.
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
		"""
		Initializes the dialog fields with account-related information.
		
		If an account instance is present, the method populates the dialog with the account's name,
		provider selection (determined by matching the account's provider name against the available providers),
		API key details (if both API key and API key storage method are provided), organization settings, 
		and a custom base URL if available. When no account is provided, it sets the API key storage method 
		combo box to its default option (index 0) and exits.
		
		Returns:
		    None
		
		Side Effects:
		    Updates UI elements such as self.name, self.provider_combo, self.api_key_storage_method_combo, 
		    and self.custom_base_url_text_ctrl, and invokes helper methods (_set_api_key_data and _init_organization_data)
		    to further process account-specific data.
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
		"""
		Set API key related UI controls using data from the account object.
		
		This method locates the index of the account's API key storage method among the available key storage methods and updates the corresponding combo box selection. It also populates the API key text control with the secret API key value retrieved from the account.
		
		Assumes:
		    - `self.account` has attributes `api_key_storage_method` and `api_key`, where `api_key` provides a `get_secret_value` method.
		    - `key_storage_methods` is a mapping of available API key storage methods.
		    - The utility functions `first` and `locate` are available for indexing operations.
		
		Returns:
		    None
		"""
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
		"""
		Initialize and populate the organization text control widget based on account provider settings and organization data.
		
		This method enables the organization text control if the provider supports organization mode. If enabled and organizations exist, it sets the control's items to a list beginning with a localized "Personal" option followed by the names of the available organizations. If an active organization ID is present, the corresponding organization (adjusted for the "Personal" offset) is selected.
		"""
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

	@property
	def provider(self) -> Provider | None:
		"""
		Retrieves the provider object corresponding to the currently selected provider name from the provider combo box.
		
		This method checks the selection state of the provider combo box using wxPython's GetSelection method.
		If a valid selection is found, it retrieves the provider name via GetValue() and returns the corresponding Provider object
		using the get_provider function. If no valid selection is present (i.e., the selection index equals wx.NOT_FOUND),
		the method returns None.
		
		Returns:
		    Provider | None: The Provider object if a valid selection exists; otherwise, None.
		"""
		provider_index = self.provider_combo.GetSelection()
		if provider_index == wx.NOT_FOUND:
			return None
		provider_name = self.provider_combo.GetValue()
		return get_provider(name=provider_name)

	def update_ui(self) -> None:
		"""
		Update the user interface components based on the currently selected provider.
		
		If no provider is set, all editable fields are disabled. Otherwise, the function updates:
		- API key fields depending on whether the provider requires an API key.
		- Organization fields based on the provider's available organization modes.
		- Custom base URL fields according to the provider's configuration.
		
		Returns:
		    None
		"""
		provider = self.provider
		if not provider:
			self._disable_all_fields()
			return

		self._update_api_key_fields(provider.require_api_key)
		self._update_organization_fields(provider.organization_mode_available)
		self._update_base_url_fields(provider)

	def _disable_all_fields(self) -> None:
		"""
		Disable all provider-dependent UI fields.
		
		This method iterates through a set of UI elements that are specific to provider configurations and disables
		each one to prevent user interaction. The disabled fields include:
		  - API key label and text control
		  - API key storage method label and combo box
		  - Organization label and text control
		  - Custom base URL label and text control
		
		Returns:
		    None
		"""
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
		"""
		Toggle the enabled state of API key input fields.
		
		This method sets the enabled/disabled state for all widgets related to API key entry,
		including the API key label, text control, and the controls for the API key storage method.
		The state is determined by the value of the 'enable' parameter.
		
		Parameters:
		    enable (bool): If True, enables all API key related fields; if False, disables them.
		
		Returns:
		    None
		"""
		fields = [
			self.api_key_label,
			self.api_key_text_ctrl,
			self.api_key_storage_method_label,
			self.api_key_storage_method_combo,
		]
		for field in fields:
			field.Enable(enable)

	def _update_organization_fields(self, enable: bool) -> None:
		"""
		Toggle the enabled state of organization-related UI widgets.
		
		This method enables or disables the organization label and associated text control based on
		the provided boolean flag. Disabling these UI components prevents user interaction when editing
		organization details is not allowed.
		
		Parameters:
		    enable (bool): If True, the organization label and text control are enabled; if False, they are disabled.
		
		Returns:
		    None
		"""
		self.organization_label.Enable(enable)
		self.organization_text_ctrl.Enable(enable)

	def _update_base_url_fields(self, provider: Provider) -> None:
		"""
		Update the custom base URL UI controls based on the provider's settings.
		
		This method enables or disables the custom base URL label and text control depending on whether the provider permits a custom base URL. If a default base URL is provided by the provider, the label is updated to display this default value; otherwise, a generic label is set.
		
		Parameters:
		    provider (Provider): An instance containing configuration data, including whether custom base URLs are allowed (allow_custom_base_url) and the default base URL (base_url).
		    
		Returns:
		    None
		"""
		self.custom_base_url_label.Enable(provider.allow_custom_base_url)
		self.custom_base_url_text_ctrl.Enable(provider.allow_custom_base_url)
		default_base_url = provider.base_url
		if default_base_url:
			self.custom_base_url_label.SetLabel(
				_("Custom &base URL (default: {})").format(default_base_url)
			)
		else:
			self.custom_base_url_label.SetLabel(_("Custom &base URL"))

	def on_ok(self, event: wx.CommandEvent) -> None:
		"""
		Handle the OK button click event.
		
		This method validates the account form. If validation fails, it displays an error message using a message box
		and sets focus to the respective field. If validation passes, the method saves the account data and closes the dialog
		with a success result.
		
		Parameters:
		    event (wx.CommandEvent): The event that triggered the OK button click.
		    
		Returns:
		    None
		"""
		error_message = self._validate_form()
		if error_message:
			msg, field = error_message
			wx.MessageBox(
				msg,
				# Translators: A title for the error message in account dialog
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			field.SetFocus()
			return

		self._save_account_data()
		self.EndModal(wx.ID_OK)

	def _validate_form(self) -> tuple[str, wx.Window] | None:
		"""
		Validate the form data and return an error message with the corresponding UI widget to focus on if a validation check fails.
		
		This method performs the following validations:
		    - Checks that the account name field is not empty.
		    - Confirms that a provider is selected.
		    - If the selected provider requires an API key, verifies that an API key storage method is chosen and that an API key is provided.
		    - If a custom base URL is allowed and provided, ensures it matches the pattern defined by CUSTOM_BASE_URL_PATTERN.
		
		Returns:
		    tuple[str, wx.Window]: A tuple containing a translated error message and the UI widget that should receive focus if a validation error occurs.
		    None: If all fields pass the validation.
		"""
		if not self.name.GetValue():
			# Translators: An error message in account dialog
			return _("Please enter a name"), self.name

		provider = self.provider
		if not provider:
			# Translators: An error message in account dialog
			return _("Please select a provider"), self.provider_combo

		if provider.require_api_key:
			if self.api_key_storage_method_combo.GetSelection() == wx.NOT_FOUND:
				# Translators: An error message in account dialog
				return _(
					"Please select an API key storage method"
				), self.api_key_storage_method_combo

			if not self.api_key_text_ctrl.GetValue():
				# Translators: An error message in account dialog
				return _(
					"Please enter an API key. It is required for this provider"
				), self.api_key_text_ctrl

		if (
			self.provider.allow_custom_base_url
			and self.custom_base_url_text_ctrl.GetValue()
		):
			if not re.match(
				CUSTOM_BASE_URL_PATTERN,
				self.custom_base_url_text_ctrl.GetValue(),
			):
				# Translators: An error message in account dialog
				return _(
					"Please enter a valid custom base URL"
				), self.custom_base_url_text_ctrl

		return None

	def _save_account_data(self) -> None:
		"""
		Save form data from the dialog into an account object.
		
		This method gathers user inputs from various UI components and processes them to either update an existing account or create a new one. It performs the following steps:
		    - Retrieves the current provider from the self.provider property.
		    - Determines the selected organization from the organization_text_ctrl. If an account with defined organizations exists and a valid selection is made (index > 0), it assigns the corresponding organization id as the active organization.
		    - If the provider requires an API key:
		        • Retrieves the API key storage method from the api_key_storage_method_combo.
		        • Wraps the API key obtained from api_key_text_ctrl with SecretStr.
		    - Obtains the custom base URL from custom_base_url_text_ctrl and sets it to None if the provider does not allow custom URLs or if the input is blank.
		    - Based on the existence of self.account, it calls:
		        • _update_existing_account(...) if the account already exists, or
		        • _create_new_account(...) to instantiate a new account with the provided data.
		
		Returns:
		    None
		
		Side Effects:
		    Updates or creates account data based on the current form inputs.
		"""
		provider = self.provider
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
		active_organization: str | None,
		api_key_storage_method: KeyStorageMethodEnum | None,
		api_key: SecretStr | None,
		custom_base_url: str | None,
	) -> None:
		"""
		Update the existing account with updated form data.
		
		This method updates the attributes of the current account instance using the values
		collected from the form controls. The account's name is retrieved from the form field,
		and its provider, API key storage method, API key, active organization identifier, and custom base URL
		are updated based on the provided parameters.
		
		Parameters:
		    provider (Provider): The provider instance to associate with the account.
		    active_organization (Optional[str]): The identifier for the active organization, or None if not set.
		    api_key_storage_method (Optional[KeyStorageMethodEnum]): The method used for storing the API key, or None.
		    api_key (Optional[SecretStr]): The API key wrapped in a SecretStr, or None.
		    custom_base_url (Optional[str]): The custom base URL for the account, or None if not specified.
		
		Returns:
		    None
		"""
		self.account.name = self.name.GetValue()
		self.account.provider = provider
		self.account.api_key_storage_method = api_key_storage_method
		self.account.api_key = api_key
		self.account.active_organization_id = active_organization
		self.account.custom_base_url = custom_base_url

	def _create_new_account(
		self,
		provider: Provider,
		active_organization: str | None,
		api_key_storage_method: KeyStorageMethodEnum | None,
		api_key: SecretStr | None,
		custom_base_url: str | None,
	) -> None:
		"""
		Create a new account using form data and the provided parameters.
		
		This method instantiates an Account object with the account name obtained from the form's 'name' field, and
		assigns it to the object's 'account' attribute. The account is configured with the specified provider, API key
		storage method, API key, active organization identifier, and custom base URL. The source of the account is set
		to AccountSource.CONFIG.
		
		Parameters:
		    provider (Provider): The provider associated with the account.
		    active_organization (str | None): The identifier of the active organization, if applicable.
		    api_key_storage_method (KeyStorageMethodEnum | None): The method to store the API key.
		    api_key (SecretStr | None): The API key for the account.
		    custom_base_url (str | None): Custom base URL for the account, if provided.
		
		Returns:
		    None
		"""
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
		"""
		Handle the Cancel button click event.
		
		Closes the dialog without saving any changes by ending the modal loop with the cancel identifier.
		
		Parameters:
		    event (wx.CommandEvent): The event object triggered by the Cancel button click.
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
		"""
		Initialize the account dialog user interface.
		
		This method creates and configures all UI components for the Account Dialog. It sets up a panel with a vertical box sizer and adds:
		  - A static text label ("Accounts") describing the section.
		  - A list control (wx.ListCtrl) to display accounts with four columns: Name, Provider, Active organization, and Source. The list control binds item selection and key down events to update the UI and handle user input.
		  - An "Add" button for creating new accounts.
		  - A "Manage organizations..." button for editing organizations related to a selected account (initially disabled).
		  - An "Edit" button for modifying a selected account (initially disabled).
		  - A "Remove" button for deleting a selected account (initially disabled).
		  - A toggle button ("Default account") to set the selected account as the default (initially disabled).
		  - A close button bound to the on_close event, with its ID set to be triggered by the Escape key.
		
		No return value.
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
