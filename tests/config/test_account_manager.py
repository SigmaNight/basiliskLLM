"""Tests for AccountManager cache cleanup behaviors."""

from unittest.mock import MagicMock

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
