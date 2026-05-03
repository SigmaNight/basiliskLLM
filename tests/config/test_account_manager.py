"""Tests for AccountManager cache cleanup behaviors."""

from unittest.mock import MagicMock
from uuid import uuid4

from basilisk.config.account_config import AccountManager


def test_remove_account_also_removes_model_cache(mocker):
	"""Removing an account should trigger model cache cleanup."""
	account = MagicMock()
	account.id = "acct-1"
	manager = AccountManager.model_construct(
		accounts=[account], default_account_info=None
	)
	remove_cache = mocker.patch(
		"basilisk.config.account_config.remove_account_model_cache"
	)
	manager.remove(account)
	account.delete_keyring_password.assert_called_once()
	remove_cache.assert_called_once_with("acct-1")
	assert account not in manager.accounts


def test_remove_default_account_clears_default_cache():
	"""Removing the default account invalidates default_account_info / cache."""
	aid = uuid4()
	account = MagicMock()
	account.id = aid
	manager = AccountManager.model_construct(
		accounts=[account], default_account_info=aid
	)
	manager.__dict__["default_account"] = account
	manager.remove(account)
	assert manager.default_account_info is None
	assert "default_account" not in manager.__dict__


def test_remove_account_best_effort_cleanup_failures(mocker):
	"""Account is removed even when keyring/cache cleanup fails."""
	account = MagicMock()
	account.id = "acct-2"
	account.delete_keyring_password.side_effect = RuntimeError("keyring down")
	manager = AccountManager.model_construct(
		accounts=[account], default_account_info=None
	)
	remove_cache = mocker.patch(
		"basilisk.config.account_config.remove_account_model_cache",
		side_effect=RuntimeError("cache locked"),
	)
	manager.remove(account)
	account.delete_keyring_password.assert_called_once()
	remove_cache.assert_called_once_with("acct-2")
	assert account not in manager.accounts
