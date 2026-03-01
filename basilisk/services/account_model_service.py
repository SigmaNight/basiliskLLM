"""Service for managing engine instances and resolving accounts/models.

Provides a wx-free service that caches engine instances per account and
resolves account/model pairs from conversation profiles.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

import basilisk.config as config

if TYPE_CHECKING:
	from basilisk.provider_engine.base_engine import BaseEngine

log = logging.getLogger(__name__)


class AccountModelService:
	"""Manages engine cache and account/model resolution.

	Attributes:
		accounts_engines: Cache of engine instances keyed by account ID.
	"""

	def __init__(self):
		"""Initialize the AccountModelService instance."""
		self.accounts_engines: dict[UUID, BaseEngine] = {}

	def get_engine(self, account: config.Account) -> BaseEngine:
		"""Get or create an engine for the given account.

		Uses lazy initialization — engines are created on first access
		and cached for subsequent calls.

		Args:
			account: The account to get an engine for.

		Returns:
			The engine instance for the account.
		"""
		if account.id not in self.accounts_engines:
			self.accounts_engines[account.id] = account.provider.engine_cls(
				account
			)
		return self.accounts_engines[account.id]

	def resolve_account_and_model(
		self,
		profile: config.ConversationProfile,
		fall_back_default_account: bool = False,
	) -> tuple[config.Account | None, str | None]:
		"""Resolve account and model ID from a profile.

		Args:
			profile: The conversation profile to resolve from.
			fall_back_default_account: Whether to fall back to the
				default account when the profile has no account or model.

		Returns:
			A tuple of (account, model_id) resolved from the profile.
			Either or both may be None if resolution fails.
		"""
		if (
			not profile.account
			and not profile.ai_model_info
			and fall_back_default_account
		):
			log.debug("no account or model in profile, use default account")
			return self._get_default_account(), None
		account = profile.account
		if profile.ai_model_info and not profile.account:
			log.debug(
				"no account in profile, trying to find account by provider"
			)
			account = next(
				config.accounts().get_accounts_by_provider(
					profile.ai_provider.name
				),
				None,
			)
		model_id = profile.ai_model_id
		return account, model_id

	def _get_default_account(self) -> config.Account | None:
		"""Get the default account from the account manager.

		Returns:
			The default account, or None if no accounts exist.
		"""
		accounts = config.accounts()
		if len(accounts) == 0:
			return None
		return accounts.default_account
