"""Tests for account presenters."""

from unittest.mock import MagicMock
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

	@pytest.mark.parametrize(
		("mutate", "expected_field"),
		[
			(lambda v: setattr(v.name.GetValue, "return_value", ""), "name"),
			(
				lambda v: setattr(
					v.key_storage_method.GetSelection, "return_value", -1
				),
				"key_storage_method",
			),
			(lambda v: setattr(v.key.GetValue, "return_value", ""), "key"),
		],
		ids=["empty_name", "no_storage", "no_key"],
	)
	def test_validate_and_build_errors(self, mock_view, mutate, expected_field):
		"""Invalid input returns (None, error) pointing to the correct field."""
		mutate(mock_view)
		presenter = EditAccountOrganizationPresenter(view=mock_view)
		result, error = presenter.validate_and_build()
		assert result is None
		assert error is not None
		assert error[1] == expected_field

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

	@pytest.mark.parametrize(
		("index", "expected"),
		[(0, True), (1, False)],
		ids=["config", "env_var"],
	)
	def test_is_editable(self, mock_account, index, expected):
		"""Config-sourced organizations are editable; ENV_VAR ones are not."""
		presenter = AccountOrganizationPresenter(mock_account)
		assert presenter.is_editable(index) is expected

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

	@pytest.mark.parametrize(
		("mutate", "expected_field"),
		[
			(lambda v: setattr(v.name.GetValue, "return_value", ""), "name"),
			(lambda v: setattr(v, "provider", None), "provider_combo"),
			(
				lambda v: setattr(
					v.api_key_storage_method_combo.GetSelection,
					"return_value",
					-1,
				),
				"api_key_storage_method_combo",
			),
			(
				lambda v: setattr(
					v.api_key_text_ctrl.GetValue, "return_value", ""
				),
				"api_key_text_ctrl",
			),
			(
				lambda v: (
					setattr(v.provider, "allow_custom_base_url", True),
					setattr(
						v.custom_base_url_text_ctrl.GetValue,
						"return_value",
						"not-a-url",
					),
				),
				"custom_base_url_text_ctrl",
			),
		],
		ids=["empty_name", "no_provider", "no_storage", "no_key", "bad_url"],
	)
	def test_validate_form_errors(self, mock_view, mutate, expected_field):
		"""Invalid form data returns an error pointing to the correct field."""
		mutate(mock_view)
		error = EditAccountPresenter(view=mock_view).validate_form()
		assert error is not None
		assert error[1] == expected_field

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

	def test_build_new_account(self, mock_view, mocker):
		"""Building a new account should create an Account."""
		mock_account_cls = mocker.patch(
			"basilisk.presenters.account_presenter.Account"
		)
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

	@pytest.mark.parametrize(
		("index", "expected"),
		[(0, True), (1, False)],
		ids=["config", "env_var"],
	)
	def test_is_editable(
		self, presenter, mock_account_manager, index, expected
	):
		"""Config-sourced accounts are editable; ENV_VAR-sourced are not."""
		assert presenter.is_editable(index) is expected

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
		"""Removing an account should remove the account object and save."""
		account = mock_account_manager[0]
		presenter.remove_account(0)
		mock_account_manager.remove.assert_called_once_with(account)
		mock_account_manager.save.assert_called_once_with()

	def test_set_default_account_toggles_on(
		self, presenter, mock_account_manager
	):
		"""Setting default on a non-default account should set it."""
		account = mock_account_manager[0]
		mock_account_manager.default_account = MagicMock()
		presenter.set_default_account(0)
		mock_account_manager.set_default_account.assert_called_once_with(
			account
		)
		mock_account_manager.save.assert_called_once_with()

	def test_set_default_account_toggles_off(
		self, presenter, mock_account_manager
	):
		"""Setting default on the current default should unset it."""
		account = mock_account_manager[0]
		mock_account_manager.default_account = account
		presenter.set_default_account(0)
		mock_account_manager.set_default_account.assert_called_once_with(None)
		mock_account_manager.save.assert_called_once()

	@pytest.mark.parametrize(
		("index", "expected"),
		[(0, True), (1, False)],
		ids=["is_default", "not_default"],
	)
	def test_is_default(self, presenter, mock_account_manager, index, expected):
		"""is_default returns True only for the default account."""
		assert presenter.is_default(index) is expected

	def test_save_organizations(self, presenter, mock_account_manager):
		"""save_organizations should reset org, replace, and save."""
		account = MagicMock()
		presenter.save_organizations(0, account)
		account.reset_active_organization.assert_called_once()
		mock_account_manager.__setitem__.assert_called_once_with(0, account)
		mock_account_manager.save.assert_called_once()
