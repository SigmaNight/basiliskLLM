"""Presenters for account dialogs.

Extracts business logic from EditAccountOrganizationDialog,
AccountOrganizationDialog, EditAccountDialog, and AccountDialog
into wx-free presenters.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import SecretStr

from basilisk.config import (
	CUSTOM_BASE_URL_PATTERN,
	Account,
	AccountOrganization,
	AccountSource,
	KeyStorageMethodEnum,
)
from basilisk.presenters.presenter_mixins import ManagerCrudMixin

if TYPE_CHECKING:
	from basilisk.config import AccountManager

key_storage_methods = KeyStorageMethodEnum.get_labels()


class EditAccountOrganizationPresenter:
	"""Presenter for the edit/create organization dialog.

	Handles validation and construction of an AccountOrganization
	from the dialog's widget values.

	Attributes:
		view: The EditAccountOrganizationDialog instance.
		organization: The organization being edited, or None for new.
	"""

	def __init__(self, view, organization: AccountOrganization | None = None):
		"""Initialize the presenter.

		Args:
			view: The dialog view with widget accessors.
			organization: Existing organization to edit, or None to create new.
		"""
		self.view = view
		self.organization = organization

	def validate_and_build(
		self,
	) -> tuple[AccountOrganization, None] | tuple[None, tuple[str, str]]:
		"""Validate inputs and build an AccountOrganization.

		Returns:
			(organization, None) on success, or
			(None, (error_msg, field_name)) on failure.
		"""
		name = self.view.name.GetValue()
		if not name:
			return None, (_("Please enter a name"), "name")

		key_selection = self.view.key_storage_method.GetSelection()
		if key_selection == -1:
			return None, (
				_("Please select a key storage method"),
				"key_storage_method",
			)

		key_value = self.view.key.GetValue()
		if not key_value:
			return None, (_("Please enter a key"), "key")

		key_storage_method = list(key_storage_methods.keys())[key_selection]

		if self.organization:
			self.organization.name = name
			self.organization.key_storage_method = key_storage_method
			self.organization.key = SecretStr(key_value)
		else:
			self.organization = AccountOrganization(
				name=name,
				key_storage_method=key_storage_method,
				key=SecretStr(key_value),
			)
		return self.organization, None


class AccountOrganizationPresenter:
	"""Presenter for the organization management dialog.

	Handles CRUD operations on organizations within an account.

	Attributes:
		account: The account whose organizations are managed.
		organizations: The working list of organizations.
	"""

	def __init__(self, account: Account):
		"""Initialize the presenter.

		Args:
			account: The account to manage organizations for.
		"""
		self.account = account
		self.organizations: list[AccountOrganization] = (
			account.organizations or []
		)

	def is_editable(self, index: int) -> bool:
		"""Check if the organization at the given index is editable.

		Args:
			index: The index of the organization.

		Returns:
			True if the organization is not from an environment variable.
		"""
		return self.organizations[index].source != AccountSource.ENV_VAR

	def add_organization(self, org: AccountOrganization):
		"""Add a new organization.

		Args:
			org: The organization to add.
		"""
		self.organizations.append(org)

	def edit_organization(self, index: int, org: AccountOrganization):
		"""Replace the organization at the given index.

		Args:
			index: The index of the organization to replace.
			org: The new organization data.
		"""
		self.organizations[index] = org

	def remove_organization(self, index: int):
		"""Remove an organization, cleaning up keyring and active org ID.

		Args:
			index: The index of the organization to remove.
		"""
		org = self.organizations[index]
		org.delete_keyring_password()
		if self.account.active_organization_id == org.id:
			self.account.active_organization_id = None
		self.organizations.pop(index)

	def save_to_account(self):
		"""Write the working organizations list back to the account."""
		self.account.organizations = self.organizations


class EditAccountPresenter:
	"""Presenter for the edit/create account dialog.

	Handles validation and construction of an Account
	from the dialog's widget values.

	Attributes:
		view: The EditAccountDialog instance.
		account: The account being edited, or None for new.
	"""

	def __init__(self, view, account: Account | None = None):
		"""Initialize the presenter.

		Args:
			view: The dialog view with widget accessors.
			account: Existing account to edit, or None to create new.
		"""
		self.view = view
		self.account = account

	def validate_form(self) -> tuple[str, str] | None:
		"""Validate form data.

		Returns:
			(error_msg, field_name) on failure, or None if valid.
		"""
		if not self.view.name.GetValue():
			return _("Please enter a name"), "name"

		provider = self.view.provider
		if not provider:
			return _("Please select a provider"), "provider_combo"

		if provider.require_api_key:
			if self.view.api_key_storage_method_combo.GetSelection() == -1:
				return (
					_("Please select an API key storage method"),
					"api_key_storage_method_combo",
				)
			if not self.view.api_key_text_ctrl.GetValue():
				return (
					_(
						"Please enter an API key. It is required for this provider"
					),
					"api_key_text_ctrl",
				)

		if (
			provider.allow_custom_base_url
			and self.view.custom_base_url_text_ctrl.GetValue()
		):
			if not re.match(
				CUSTOM_BASE_URL_PATTERN,
				self.view.custom_base_url_text_ctrl.GetValue(),
			):
				return (
					_("Please enter a valid custom base URL"),
					"custom_base_url_text_ctrl",
				)

		return None

	def build_account(self) -> Account:
		"""Build account from form data. Call after validate_form() returns None.

		Returns:
			The built or updated Account.
		"""
		provider = self.view.provider
		organization_index = self.view.organization_text_ctrl.GetSelection()
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
				self.view.api_key_storage_method_combo.GetSelection()
			]
			api_key = SecretStr(self.view.api_key_text_ctrl.GetValue())

		custom_base_url = self.view.custom_base_url_text_ctrl.GetValue()
		if not provider.allow_custom_base_url or not custom_base_url.strip():
			custom_base_url = None

		if self.account:
			self.account.name = self.view.name.GetValue()
			self.account.provider = provider
			self.account.api_key_storage_method = api_key_storage_method
			self.account.api_key = api_key
			self.account.active_organization_id = active_organization
			self.account.custom_base_url = custom_base_url
		else:
			self.account = Account(
				name=self.view.name.GetValue(),
				provider=provider,
				api_key_storage_method=api_key_storage_method,
				api_key=api_key,
				active_organization_id=active_organization,
				source=AccountSource.CONFIG,
				custom_base_url=custom_base_url,
			)
		return self.account


class AccountPresenter(ManagerCrudMixin):
	"""Presenter for the account management dialog.

	Handles CRUD operations and persistence for accounts.

	Attributes:
		account_manager: The account manager for persistence.
	"""

	def __init__(self, account_manager: AccountManager):
		"""Initialize the presenter.

		Args:
			account_manager: The account manager instance.
		"""
		self.account_manager = account_manager

	@property
	def manager(self):
		"""Return the backing account manager."""
		return self.account_manager

	def _before_edit(self, index: int, account: Account) -> None:
		"""Reset the active organization before replacing an account.

		Args:
			index: Position of the account being replaced.
			account: The replacement account.
		"""
		account.reset_active_organization()

	def is_editable(self, index: int) -> bool:
		"""Check if the account at the given index is editable.

		Args:
			index: The index of the account.

		Returns:
			True if the account is not from an environment variable.
		"""
		return self.account_manager[index].source != AccountSource.ENV_VAR

	def get_organization_display_name(self, account: Account) -> str:
		"""Get a display name for the active organization.

		Args:
			account: The account to get the organization name for.

		Returns:
			The organization name or "No (personal)".
		"""
		if not account.active_organization:
			return _("No (personal)")
		return account.active_organization.name

	def add_account(self, account: Account):
		"""Add a new account and save.

		Args:
			account: The account to add.
		"""
		self.add_item(account)

	def edit_account(self, index: int, account: Account):
		"""Replace an account at the given index and save.

		Args:
			index: The index of the account to replace.
			account: The new account data.
		"""
		self.edit_item(index, account)

	def remove_account(self, index: int):
		"""Remove an account at the given index and save.

		Args:
			index: The index of the account to remove.
		"""
		self.remove_item_by_index(index)

	def save_organizations(self, index: int, account: Account):
		"""Save organization changes for an account and save.

		Args:
			index: The index of the account.
			account: The account with updated organizations.
		"""
		self.edit_item(index, account)

	def set_default_account(self, index: int):
		"""Toggle the default account at the given index and save.

		Args:
			index: The index of the account.
		"""
		account = self.account_manager[index]
		if self.account_manager.default_account == account:
			self.account_manager.set_default_account(None)
		else:
			self.account_manager.set_default_account(account)
		self.account_manager.save()

	def is_default(self, index: int) -> bool:
		"""Check if the account at the given index is the default.

		Args:
			index: The index of the account.

		Returns:
			True if the account is the default.
		"""
		return (
			self.account_manager.default_account == self.account_manager[index]
		)
