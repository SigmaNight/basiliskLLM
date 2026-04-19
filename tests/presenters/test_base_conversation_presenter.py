"""Tests for BaseConversationPresenter."""

from unittest.mock import MagicMock

import pytest

from basilisk.presenters.base_conversation_presenter import (
	BaseConversationPresenter,
)
from basilisk.provider_ai_model import ProviderAIModel
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


# ---------------------------------------------------------------------------
# shutdown_model_loading()
# ---------------------------------------------------------------------------


class TestShutdownModelLoading:
	"""Tests for BaseConversationPresenter.shutdown_model_loading()."""

	def test_increments_generation(self, presenter):
		"""shutdown_model_loading() increments _model_loading_generation."""
		assert presenter._model_loading_generation == 0
		presenter.shutdown_model_loading()
		assert presenter._model_loading_generation == 1

	def test_sets_cancel_event(self, presenter):
		"""shutdown_model_loading() calls set() on the existing cancel event."""
		cancel_event = MagicMock()
		presenter._model_loading_cancel_event = cancel_event
		presenter.shutdown_model_loading()
		cancel_event.set.assert_called_once()

	def test_clears_thread_and_event_refs(self, presenter):
		"""shutdown_model_loading() sets thread and cancel event refs to None."""
		presenter._model_loading_thread = MagicMock()
		presenter._model_loading_cancel_event = MagicMock()
		presenter.shutdown_model_loading()
		assert presenter._model_loading_thread is None
		assert presenter._model_loading_cancel_event is None

	def test_no_error_when_no_cancel_event(self, presenter):
		"""shutdown_model_loading() does not raise when cancel event is None."""
		presenter._model_loading_cancel_event = None
		presenter.shutdown_model_loading()  # must not raise


# ---------------------------------------------------------------------------
# set_pending_model()
# ---------------------------------------------------------------------------


class TestSetPendingModel:
	"""Tests for BaseConversationPresenter.set_pending_model()."""

	def test_stores_model_id_and_account_id(self, presenter):
		"""set_pending_model() stores both identifiers on the presenter."""
		presenter.set_pending_model("gpt-4", "acct-1")
		assert presenter._pending_model_id == "gpt-4"
		assert presenter._pending_model_account_id == "acct-1"


# ---------------------------------------------------------------------------
# pop_pending_model()
# ---------------------------------------------------------------------------


def _make_provider_model(model_id: str) -> MagicMock:
	"""Return a mock ProviderAIModel with the given id."""
	m = MagicMock(spec=ProviderAIModel)
	m.id = model_id
	return m


class TestPopPendingModel:
	"""Tests for BaseConversationPresenter.pop_pending_model()."""

	def test_returns_none_when_no_pending(self, presenter):
		"""Returns None when no pending model is set."""
		result = presenter.pop_pending_model([], "acct-1")
		assert result is None

	def test_returns_none_when_wrong_account(self, presenter):
		"""Returns None when the account_id does not match."""
		presenter.set_pending_model("gpt-4", "acct-1")
		result = presenter.pop_pending_model(
			[_make_provider_model("gpt-4")], "acct-2"
		)
		assert result is None

	def test_returns_none_when_no_displayed_models(self, presenter):
		"""Returns None when displayed_models is empty."""
		presenter.set_pending_model("gpt-4", "acct-1")
		result = presenter.pop_pending_model([], "acct-1")
		assert result is None

	def test_returns_matching_model_and_clears_state(self, presenter):
		"""Returns the matching model and resets pending state."""
		model = _make_provider_model("gpt-4")
		presenter.set_pending_model("gpt-4", "acct-1")
		result = presenter.pop_pending_model([model], "acct-1")
		assert result is model
		assert presenter._pending_model_id is None
		assert presenter._pending_model_account_id is None

	def test_returns_none_when_model_not_found(self, presenter):
		"""Returns None when no displayed model matches the pending id."""
		presenter.set_pending_model("gpt-4", "acct-1")
		result = presenter.pop_pending_model(
			[_make_provider_model("claude-3")], "acct-1"
		)
		assert result is None
		assert presenter._pending_model_id is None
		assert presenter._pending_model_account_id is None


# ---------------------------------------------------------------------------
# _load_models_in_background()
# ---------------------------------------------------------------------------


class TestLoadModelsInBackground:
	"""Tests for BaseConversationPresenter._load_models_in_background()."""

	def _make_engine(self, models=None, error=None):
		engine = MagicMock()
		engine.models = models or []
		engine.get_model_loading_error.return_value = error
		return engine

	def test_calls_on_loaded_with_models(self, presenter, mocker):
		"""Calls wx.CallAfter(on_loaded, account_id, models, None) on success."""
		mock_call_after = mocker.patch("wx.CallAfter")
		on_loaded = MagicMock()
		model = _make_provider_model("gpt-4")
		engine = self._make_engine(models=[model])
		cancel_event = MagicMock()
		cancel_event.is_set.return_value = False
		presenter._load_models_in_background(
			"acct-1", engine, 0, cancel_event, on_loaded
		)
		mock_call_after.assert_called_once_with(
			on_loaded, "acct-1", [model], None
		)

	def test_skips_callback_when_cancelled(self, presenter, mocker):
		"""Does not call wx.CallAfter when cancel_event is set."""
		mock_call_after = mocker.patch("wx.CallAfter")
		on_loaded = MagicMock()
		engine = self._make_engine(models=[_make_provider_model("gpt-4")])
		cancel_event = MagicMock()
		cancel_event.is_set.return_value = True
		presenter._load_models_in_background(
			"acct-1", engine, 0, cancel_event, on_loaded
		)
		mock_call_after.assert_not_called()

	def test_skips_callback_when_generation_stale(self, presenter, mocker):
		"""Does not call wx.CallAfter when generation counter has advanced."""
		mock_call_after = mocker.patch("wx.CallAfter")
		on_loaded = MagicMock()
		engine = self._make_engine(models=[_make_provider_model("gpt-4")])
		cancel_event = MagicMock()
		cancel_event.is_set.return_value = False
		presenter._model_loading_generation = 1  # advanced past generation 0
		presenter._load_models_in_background(
			"acct-1", engine, 0, cancel_event, on_loaded
		)
		mock_call_after.assert_not_called()

	def test_invalidates_cache_on_error_with_no_models(self, presenter, mocker):
		"""Calls invalidate_models_cache() when there is an error but no models."""
		mocker.patch("wx.CallAfter")
		on_loaded = MagicMock()
		engine = self._make_engine(models=[], error="Network error")
		cancel_event = MagicMock()
		cancel_event.is_set.return_value = False
		presenter._load_models_in_background(
			"acct-1", engine, 0, cancel_event, on_loaded
		)
		engine.invalidate_models_cache.assert_called_once()

	def test_exception_yields_empty_models_and_error(self, presenter, mocker):
		"""On exception, calls wx.CallAfter with empty models and an error message."""
		mock_call_after = mocker.patch("wx.CallAfter")
		on_loaded = MagicMock()
		engine = MagicMock()
		engine.models = MagicMock(side_effect=RuntimeError("boom"))
		cancel_event = MagicMock()
		cancel_event.is_set.return_value = False
		presenter._load_models_in_background(
			"acct-1", engine, 0, cancel_event, on_loaded
		)
		mock_call_after.assert_called_once()
		__, account_id, models, error_message = mock_call_after.call_args[0]
		assert account_id == "acct-1"
		assert models == []
		assert error_message is not None
