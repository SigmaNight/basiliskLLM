"""Tests for account presenters."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import SecretStr

from basilisk.config import AccountOrganization, AccountSource
from basilisk.presenters.account_presenter import (
	AccountOrganizationPresenter,
	AccountPresenter,
	EditAccountOrganizationPresenter,
	EditAccountPresenter,
)


class TestEditAccountOrganizationPresenter:
	"""Tests for EditAccountOrganizationPresenter."""

	@pytest.fixture
	def mock_view(self):
		"""Return a mock view with required widget accessors."""
		view = MagicMock()
		view.name.GetValue.return_value = "Test Org"
		view.key_storage_method.GetSelection.return_value = 0
		view.key.GetValue.return_value = "secret-key"
		return view

	def test_validate_empty_name_returns_error(self, mock_view):
		"""Empty name should return error."""
		mock_view.name.GetValue.return_value = ""
		presenter = EditAccountOrganizationPresenter(view=mock_view)
		result, error = presenter.validate_and_build()
		assert result is None
		assert error is not None
		assert error[1] == "name"

	def test_validate_no_key_storage_method_returns_error(self, mock_view):
		"""No key storage method selected should return error."""
		mock_view.key_storage_method.GetSelection.return_value = -1
		presenter = EditAccountOrganizationPresenter(view=mock_view)
		result, error = presenter.validate_and_build()
		assert result is None
		assert error[1] == "key_storage_method"

	def test_validate_empty_key_returns_error(self, mock_view):
		"""Empty key should return error."""
		mock_view.key.GetValue.return_value = ""
		presenter = EditAccountOrganizationPresenter(view=mock_view)
		result, error = presenter.validate_and_build()
		assert result is None
		assert error[1] == "key"

	def test_validate_builds_new_organization(self, mock_view):
		"""Valid inputs should build a new organization."""
		presenter = EditAccountOrganizationPresenter(view=mock_view)
		result, error = presenter.validate_and_build()
		assert error is None
		assert result is not None
		assert result.name == "Test Org"
		assert result.key.get_secret_value() == "secret-key"

	def test_validate_updates_existing_organization(self, mock_view):
		"""Editing an existing organization should update it in place."""
		existing = AccountOrganization(name="Old Org", key=SecretStr("old-key"))
		presenter = EditAccountOrganizationPresenter(
			view=mock_view, organization=existing
		)
		result, error = presenter.validate_and_build()
		assert error is None
		assert result is existing
		assert result.name == "Test Org"
		assert result.key.get_secret_value() == "secret-key"


class TestAccountOrganizationPresenter:
	"""Tests for AccountOrganizationPresenter."""

	@pytest.fixture
	def mock_account(self):
		"""Return a mock account with organizations."""
		account = MagicMock()
		org1 = MagicMock(spec=AccountOrganization)
		org1.source = AccountSource.CONFIG
		org1.id = uuid4()
		org2 = MagicMock(spec=AccountOrganization)
		org2.source = AccountSource.ENV_VAR
		org2.id = uuid4()
		account.organizations = [org1, org2]
		account.active_organization_id = None
		return account

	def test_is_editable_true_for_config(self, mock_account):
		"""Config-sourced organization should be editable."""
		presenter = AccountOrganizationPresenter(mock_account)
		assert presenter.is_editable(0) is True

	def test_is_editable_false_for_env_var(self, mock_account):
		"""ENV_VAR-sourced organization should not be editable."""
		presenter = AccountOrganizationPresenter(mock_account)
		assert presenter.is_editable(1) is False

	def test_add_organization(self, mock_account):
		"""Adding an organization should append it."""
		presenter = AccountOrganizationPresenter(mock_account)
		new_org = MagicMock(spec=AccountOrganization)
		presenter.add_organization(new_org)
		assert len(presenter.organizations) == 3
		assert presenter.organizations[-1] is new_org

	def test_edit_organization(self, mock_account):
		"""Editing should replace organization at index."""
		presenter = AccountOrganizationPresenter(mock_account)
		new_org = MagicMock(spec=AccountOrganization)
		presenter.edit_organization(0, new_org)
		assert presenter.organizations[0] is new_org

	def test_remove_organization_cleans_keyring(self, mock_account):
		"""Removing should call delete_keyring_password."""
		presenter = AccountOrganizationPresenter(mock_account)
		org = presenter.organizations[0]
		presenter.remove_organization(0)
		org.delete_keyring_password.assert_called_once()
		assert len(presenter.organizations) == 1

	def test_remove_clears_active_org_id_if_match(self, mock_account):
		"""Removing the active organization should clear the active_organization_id."""
		org_id = mock_account.organizations[0].id
		mock_account.active_organization_id = org_id
		presenter = AccountOrganizationPresenter(mock_account)
		presenter.remove_organization(0)
		assert mock_account.active_organization_id is None

	def test_remove_preserves_active_org_id_if_no_match(self, mock_account):
		"""Removing a non-active organization should keep active_organization_id."""
		other_id = uuid4()
		mock_account.active_organization_id = other_id
		presenter = AccountOrganizationPresenter(mock_account)
		presenter.remove_organization(0)
		assert mock_account.active_organization_id == other_id

	def test_save_to_account(self, mock_account):
		"""save_to_account should write organizations back to account."""
		presenter = AccountOrganizationPresenter(mock_account)
		new_org = MagicMock(spec=AccountOrganization)
		presenter.add_organization(new_org)
		presenter.save_to_account()
		assert mock_account.organizations is presenter.organizations


class TestEditAccountPresenter:
	"""Tests for EditAccountPresenter."""

	@pytest.fixture
	def mock_view(self):
		"""Return a mock view with required widget accessors."""
		view = MagicMock()
		view.name.GetValue.return_value = "Test Account"
		provider = MagicMock()
		provider.require_api_key = True
		provider.allow_custom_base_url = False
		provider.organization_mode_available = False
		view.provider = provider
		view.api_key_storage_method_combo.GetSelection.return_value = 0
		view.api_key_text_ctrl.GetValue.return_value = "sk-test"
		view.custom_base_url_text_ctrl.GetValue.return_value = ""
		view.organization_text_ctrl.GetSelection.return_value = -1
		return view

	def test_validate_empty_name(self, mock_view):
		"""Empty name should return error."""
		mock_view.name.GetValue.return_value = ""
		presenter = EditAccountPresenter(view=mock_view)
		error = presenter.validate_form()
		assert error is not None
		assert error[1] == "name"

	def test_validate_no_provider(self, mock_view):
		"""No provider selected should return error."""
		mock_view.provider = None
		presenter = EditAccountPresenter(view=mock_view)
		error = presenter.validate_form()
		assert error is not None
		assert error[1] == "provider_combo"

	def test_validate_missing_api_key_storage_method(self, mock_view):
		"""Missing API key storage method should return error."""
		mock_view.api_key_storage_method_combo.GetSelection.return_value = -1
		presenter = EditAccountPresenter(view=mock_view)
		error = presenter.validate_form()
		assert error is not None
		assert error[1] == "api_key_storage_method_combo"

	def test_validate_missing_api_key(self, mock_view):
		"""Missing API key should return error."""
		mock_view.api_key_text_ctrl.GetValue.return_value = ""
		presenter = EditAccountPresenter(view=mock_view)
		error = presenter.validate_form()
		assert error is not None
		assert error[1] == "api_key_text_ctrl"

	def test_validate_invalid_base_url(self, mock_view):
		"""Invalid custom base URL should return error."""
		mock_view.provider.allow_custom_base_url = True
		mock_view.custom_base_url_text_ctrl.GetValue.return_value = "not-a-url"
		presenter = EditAccountPresenter(view=mock_view)
		error = presenter.validate_form()
		assert error is not None
		assert error[1] == "custom_base_url_text_ctrl"

	def test_validate_success(self, mock_view):
		"""Valid form data should return None."""
		presenter = EditAccountPresenter(view=mock_view)
		error = presenter.validate_form()
		assert error is None

	def test_validate_no_api_key_required(self, mock_view):
		"""Provider not requiring API key should skip key validation."""
		mock_view.provider.require_api_key = False
		mock_view.api_key_text_ctrl.GetValue.return_value = ""
		presenter = EditAccountPresenter(view=mock_view)
		error = presenter.validate_form()
		assert error is None

	@patch("basilisk.presenters.account_presenter.Account")
	def test_build_new_account(self, mock_account_cls, mock_view):
		"""Building a new account should create an Account."""
		presenter = EditAccountPresenter(view=mock_view)
		result = presenter.build_account()
		mock_account_cls.assert_called_once()
		assert result is mock_account_cls.return_value

	def test_build_updates_existing_account(self, mock_view):
		"""Building with an existing account should update it."""
		existing = MagicMock()
		existing.organizations = None
		presenter = EditAccountPresenter(view=mock_view, account=existing)
		result = presenter.build_account()
		assert result is existing
		assert existing.name == "Test Account"
		assert existing.provider is mock_view.provider


class TestAccountPresenter:
	"""Tests for AccountPresenter."""

	@pytest.fixture
	def mock_account_manager(self):
		"""Return a mock AccountManager."""
		manager = MagicMock()
		account1 = MagicMock()
		account1.source = AccountSource.CONFIG
		account1.active_organization = None
		account2 = MagicMock()
		account2.source = AccountSource.ENV_VAR
		account2.active_organization = MagicMock()
		account2.active_organization.name = "Test Org"
		manager.__getitem__ = MagicMock(
			side_effect=lambda i: [account1, account2][i]
		)
		manager.default_account = account1
		return manager

	@pytest.fixture
	def presenter(self, mock_account_manager):
		"""Return a presenter with mock dependencies."""
		return AccountPresenter(mock_account_manager)

	def test_is_editable_true_for_config(self, presenter, mock_account_manager):
		"""Config-sourced account should be editable."""
		assert presenter.is_editable(0) is True

	def test_is_editable_false_for_env_var(
		self, presenter, mock_account_manager
	):
		"""ENV_VAR-sourced account should not be editable."""
		assert presenter.is_editable(1) is False

	def test_get_organization_display_name_no_org(self, presenter):
		"""No active organization should return 'No (personal)'."""
		account = MagicMock()
		account.active_organization = None
		result = presenter.get_organization_display_name(account)
		assert result == "No (personal)"

	def test_get_organization_display_name_with_org(self, presenter):
		"""Active organization should return its name."""
		account = MagicMock()
		account.active_organization = MagicMock()
		account.active_organization.name = "My Org"
		result = presenter.get_organization_display_name(account)
		assert result == "My Org"

	def test_add_account_saves(self, presenter, mock_account_manager):
		"""Adding an account should add and save."""
		account = MagicMock()
		presenter.add_account(account)
		mock_account_manager.add.assert_called_once_with(account)
		mock_account_manager.save.assert_called_once()

	def test_edit_account_saves(self, presenter, mock_account_manager):
		"""Editing an account should reset org, replace, and save."""
		account = MagicMock()
		presenter.edit_account(0, account)
		account.reset_active_organization.assert_called_once()
		mock_account_manager.__setitem__.assert_called_once_with(0, account)
		mock_account_manager.save.assert_called_once()

	def test_remove_account_saves(self, presenter, mock_account_manager):
		"""Removing an account should remove and save."""
		presenter.remove_account(0)
		mock_account_manager.remove.assert_called_once()
		mock_account_manager.save.assert_called_once()

	def test_set_default_account_toggles_on(
		self, presenter, mock_account_manager
	):
		"""Setting default on a non-default account should set it."""
		mock_account_manager.default_account = MagicMock()
		presenter.set_default_account(0)
		mock_account_manager.set_default_account.assert_called_once()
		mock_account_manager.save.assert_called_once()

	def test_set_default_account_toggles_off(
		self, presenter, mock_account_manager
	):
		"""Setting default on the current default should unset it."""
		account = mock_account_manager[0]
		mock_account_manager.default_account = account
		presenter.set_default_account(0)
		mock_account_manager.set_default_account.assert_called_once_with(None)
		mock_account_manager.save.assert_called_once()

	def test_is_default_true(self, presenter, mock_account_manager):
		"""is_default should return True for the default account."""
		assert presenter.is_default(0) is True

	def test_is_default_false(self, presenter, mock_account_manager):
		"""is_default should return False for non-default accounts."""
		assert presenter.is_default(1) is False

	def test_save_organizations(self, presenter, mock_account_manager):
		"""save_organizations should reset org, replace, and save."""
		account = MagicMock()
		presenter.save_organizations(0, account)
		account.reset_active_organization.assert_called_once()
		mock_account_manager.__setitem__.assert_called_once_with(0, account)
		mock_account_manager.save.assert_called_once()
