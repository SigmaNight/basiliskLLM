"""Presenter providing account/model resolution logic for conversation views.

Extracts the pure, testable parts of BaseConversation into a wx-free
presenter that can be shared between ConversationTab and any future
conversation panel.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import basilisk.config as config
from basilisk.services.account_model_service import AccountModelService

if TYPE_CHECKING:
	from basilisk.provider_engine.base_engine import BaseEngine

log = logging.getLogger(__name__)


class BaseConversationPresenter:
	"""Presenter for account and model resolution in conversation views.

	Owns the AccountModelService and provides pure, testable methods for
	resolving accounts and models for display in conversation views.

	Attributes:
		account_model_service: Service for engine cache and
			account/model resolution.
	"""

	def __init__(
		self, account_model_service: Optional[AccountModelService] = None
	) -> None:
		"""Initialize the presenter.

		Args:
			account_model_service: Service instance; a new one is
				created if not provided.
		"""
		self.account_model_service: AccountModelService = (
			account_model_service or AccountModelService()
		)

	def get_engine(self, account: config.Account) -> BaseEngine:
		"""Get or create an engine for the given account.

		Args:
			account: The account to get an engine for.

		Returns:
			The engine instance for the account.
		"""
		return self.account_model_service.get_engine(account)

	def get_display_accounts(self, force_refresh: bool = False) -> list[str]:
		"""Return a list of account display names.

		Args:
			force_refresh: When True, each account's active organisation
				is reset before reading its display name.

		Returns:
			Ordered list of display name strings.
		"""
		accounts = []
		for account in config.accounts():
			if force_refresh:
				account.reset_active_organization()
			accounts.append(account.display_name)
		return accounts

	def get_display_models(self, engine: Optional[BaseEngine]) -> list[tuple]:
		"""Return model display tuples for the given engine.

		Args:
			engine: The engine whose models to list, or None.

		Returns:
			List of display tuples (one per model), empty if no engine.
		"""
		if not engine:
			return []
		return [m.display_model for m in engine.models]

	def resolve_account_and_model(
		self,
		profile: config.ConversationProfile,
		fall_back_default_account: bool = False,
	) -> tuple[Optional[config.Account], Optional[str]]:
		"""Resolve account and model ID from a conversation profile.

		Delegates to AccountModelService.

		Args:
			profile: The conversation profile to resolve from.
			fall_back_default_account: Whether to fall back to the
				default account when the profile has none.

		Returns:
			A tuple of (account, model_id); either may be None.
		"""
		return self.account_model_service.resolve_account_and_model(
			profile, fall_back_default_account
		)
