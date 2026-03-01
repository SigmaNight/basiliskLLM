"""Tests for BaseConversationPresenter."""

from unittest.mock import MagicMock

import pytest

from basilisk.presenters.base_conversation_presenter import (
	BaseConversationPresenter,
)
from basilisk.services.account_model_service import AccountModelService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_service():
	"""Return a mock AccountModelService."""
	return MagicMock(spec=AccountModelService)


@pytest.fixture
def presenter(mock_service):
	"""Return a BaseConversationPresenter with a mock service."""
	return BaseConversationPresenter(account_model_service=mock_service)


# ---------------------------------------------------------------------------
# Helpers (used inline for custom state)
# ---------------------------------------------------------------------------


def _make_account(display_name: str) -> MagicMock:
	"""Return a mock Account with the given display name.

	Args:
		display_name: The account display name.

	Returns:
		A MagicMock account.
	"""
	account = MagicMock()
	account.display_name = display_name
	return account


def _make_model(display_model: tuple) -> MagicMock:
	"""Return a mock ProviderAIModel whose display_model is the given tuple.

	Args:
		display_model: The display tuple.

	Returns:
		A MagicMock model.
	"""
	model = MagicMock()
	model.display_model = display_model
	return model


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestBaseConversationPresenterInit:
	"""Tests for BaseConversationPresenter.__init__."""

	def test_creates_service_when_not_provided(self):
		"""A new AccountModelService is created when none is passed."""
		p = BaseConversationPresenter()
		assert isinstance(p.account_model_service, AccountModelService)

	def test_uses_provided_service(self, mock_service):
		"""The provided service instance is stored unchanged."""
		p = BaseConversationPresenter(account_model_service=mock_service)
		assert p.account_model_service is mock_service


# ---------------------------------------------------------------------------
# get_display_accounts()
# ---------------------------------------------------------------------------


class TestGetDisplayAccounts:
	"""Tests for BaseConversationPresenter.get_display_accounts()."""

	def test_returns_list_of_display_names(self, presenter, mocker):
		"""Returns a list with each account's display_name."""
		accounts = [_make_account("Alice"), _make_account("Bob")]
		mocker.patch("basilisk.config.accounts", return_value=accounts)
		result = presenter.get_display_accounts()
		assert result == ["Alice", "Bob"]

	def test_empty_when_no_accounts(self, presenter, mocker):
		"""Returns [] when there are no accounts."""
		mocker.patch("basilisk.config.accounts", return_value=[])
		assert presenter.get_display_accounts() == []

	def test_force_refresh_calls_reset_active_organization(
		self, presenter, mocker
	):
		"""force_refresh=True calls reset_active_organization on each account."""
		accounts = [_make_account("X"), _make_account("Y")]
		mocker.patch("basilisk.config.accounts", return_value=accounts)
		presenter.get_display_accounts(force_refresh=True)
		for account in accounts:
			account.reset_active_organization.assert_called_once()

	def test_no_reset_when_force_refresh_false(self, presenter, mocker):
		"""force_refresh=False does not call reset_active_organization."""
		accounts = [_make_account("X")]
		mocker.patch("basilisk.config.accounts", return_value=accounts)
		presenter.get_display_accounts(force_refresh=False)
		accounts[0].reset_active_organization.assert_not_called()


# ---------------------------------------------------------------------------
# get_display_models()
# ---------------------------------------------------------------------------


class TestGetDisplayModels:
	"""Tests for BaseConversationPresenter.get_display_models()."""

	def test_returns_empty_when_no_engine(self, presenter):
		"""Returns [] when engine is None."""
		assert presenter.get_display_models(None) == []

	def test_returns_display_model_tuples(self, presenter):
		"""Returns display_model for each model in the engine."""
		engine = MagicMock()
		engine.models = [
			_make_model(("GPT-4", "Yes", "128k", "4096")),
			_make_model(("GPT-3.5", "No", "16k", "2048")),
		]
		result = presenter.get_display_models(engine)
		assert result == [
			("GPT-4", "Yes", "128k", "4096"),
			("GPT-3.5", "No", "16k", "2048"),
		]

	def test_returns_empty_when_engine_has_no_models(self, presenter):
		"""Returns [] when the engine's model list is empty."""
		engine = MagicMock()
		engine.models = []
		assert presenter.get_display_models(engine) == []


# ---------------------------------------------------------------------------
# get_engine()
# ---------------------------------------------------------------------------


class TestGetEngine:
	"""Tests for BaseConversationPresenter.get_engine()."""

	def test_delegates_to_service(self, mock_service):
		"""get_engine() calls account_model_service.get_engine()."""
		engine = MagicMock()
		mock_service.get_engine.return_value = engine
		p = BaseConversationPresenter(account_model_service=mock_service)
		account = MagicMock()
		result = p.get_engine(account)
		mock_service.get_engine.assert_called_once_with(account)
		assert result is engine


# ---------------------------------------------------------------------------
# resolve_account_and_model()
# ---------------------------------------------------------------------------


class TestResolveAccountAndModel:
	"""Tests for BaseConversationPresenter.resolve_account_and_model()."""

	def test_delegates_to_service(self, mock_service):
		"""resolve_account_and_model() delegates to the service."""
		account = MagicMock()
		mock_service.resolve_account_and_model.return_value = (account, "gpt-4")
		p = BaseConversationPresenter(account_model_service=mock_service)
		profile = MagicMock()
		result = p.resolve_account_and_model(
			profile, fall_back_default_account=True
		)
		mock_service.resolve_account_and_model.assert_called_once_with(
			profile, True
		)
		assert result == (account, "gpt-4")

	def test_returns_none_none_when_no_account_or_model(self, mock_service):
		"""Returns (None, None) when the service returns no account or model."""
		mock_service.resolve_account_and_model.return_value = (None, None)
		p = BaseConversationPresenter(account_model_service=mock_service)
		profile = MagicMock()
		account, model_id = p.resolve_account_and_model(profile)
		assert account is None
		assert model_id is None
