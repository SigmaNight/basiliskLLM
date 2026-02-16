"""Tests for AccountModelService."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from basilisk.services.account_model_service import AccountModelService


@pytest.fixture
def service():
	"""Return a fresh AccountModelService."""
	return AccountModelService()


@pytest.fixture
def mock_account():
	"""Return a mock Account with a unique ID and provider."""
	account = MagicMock()
	account.id = uuid4()
	account.provider.engine_cls.return_value = MagicMock()
	account.provider.name = "openai"
	account.provider.id = "openai"
	return account


class TestGetEngine:
	"""Tests for get_engine."""

	def test_creates_engine_on_first_call(self, service, mock_account):
		"""First call should create a new engine via engine_cls."""
		engine = service.get_engine(mock_account)
		mock_account.provider.engine_cls.assert_called_once_with(mock_account)
		assert engine is mock_account.provider.engine_cls.return_value

	def test_caches_engine_on_subsequent_calls(self, service, mock_account):
		"""Subsequent calls should return the cached engine."""
		engine1 = service.get_engine(mock_account)
		engine2 = service.get_engine(mock_account)
		assert engine1 is engine2
		mock_account.provider.engine_cls.assert_called_once()

	def test_different_accounts_get_different_engines(self, service):
		"""Different accounts should get separate engine instances."""
		account1 = MagicMock()
		account1.id = uuid4()
		account1.provider.engine_cls.return_value = MagicMock()

		account2 = MagicMock()
		account2.id = uuid4()
		account2.provider.engine_cls.return_value = MagicMock()

		engine1 = service.get_engine(account1)
		engine2 = service.get_engine(account2)
		assert engine1 is not engine2


class TestResolveAccountAndModel:
	"""Tests for resolve_account_and_model."""

	def test_returns_account_and_model_from_profile(
		self, service, mock_account
	):
		"""Profile with account and model should resolve both."""
		profile = MagicMock()
		profile.account = mock_account
		profile.ai_model_info = MagicMock()
		profile.ai_model_id = "gpt-4"

		account, model_id = service.resolve_account_and_model(profile)
		assert account is mock_account
		assert model_id == "gpt-4"

	def test_falls_back_to_default_when_no_account_or_model(self, service):
		"""Empty profile with fallback should return default account."""
		profile = MagicMock()
		profile.account = None
		profile.ai_model_info = None

		mock_default = MagicMock()
		with patch(
			"basilisk.services.account_model_service.config"
		) as mock_config:
			mock_config.accounts.return_value.__len__ = lambda self: 1
			mock_config.accounts.return_value.default_account = mock_default
			account, model_id = service.resolve_account_and_model(
				profile, fall_back_default_account=True
			)
		assert account is mock_default
		assert model_id is None

	def test_finds_account_by_provider_when_no_account(self, service):
		"""Profile with model but no account should find account by provider."""
		profile = MagicMock()
		profile.account = None
		profile.ai_model_info = MagicMock()
		profile.ai_model_id = "gpt-4"
		profile.ai_provider.name = "openai"

		found_account = MagicMock()
		with patch(
			"basilisk.services.account_model_service.config"
		) as mock_config:
			mock_config.accounts.return_value.get_accounts_by_provider.return_value = iter(
				[found_account]
			)
			account, model_id = service.resolve_account_and_model(profile)
		assert account is found_account
		assert model_id == "gpt-4"

	def test_returns_none_when_no_match(self, service):
		"""Profile with no account and no fallback should return None."""
		profile = MagicMock()
		profile.account = None
		profile.ai_model_info = None
		profile.ai_model_id = None

		account, model_id = service.resolve_account_and_model(
			profile, fall_back_default_account=False
		)
		assert account is None
		assert model_id is None
