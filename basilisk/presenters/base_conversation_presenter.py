"""Presenter providing account/model resolution logic for conversation views.

Extracts the pure, testable parts of BaseConversation into a wx-free
presenter that can be shared between ConversationTab and any future
conversation panel.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Callable

import basilisk.config as config
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.services.account_model_service import AccountModelService

if TYPE_CHECKING:
	from uuid import UUID

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
		self, account_model_service: AccountModelService | None = None
	) -> None:
		"""Initialize the presenter.

		Args:
			account_model_service: Service instance; a new one is
				created if not provided.
		"""
		self.account_model_service: AccountModelService = (
			account_model_service or AccountModelService()
		)
		self._model_loading_thread: threading.Thread | None = None
		self._model_loading_cancel_event: threading.Event | None = None
		self._model_loading_generation: int = 0
		self._pending_model_id: str | None = None
		self._pending_model_account_id: UUID | None = None

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

	def get_display_models(self, engine: BaseEngine | None) -> list[tuple]:
		"""Return model display tuples for the given engine.

		Args:
			engine: The engine whose models to list, or None.

		Returns:
			List of display tuples (one per model), empty if no engine.
		"""
		if not engine:
			return []
		return [m.display_model for m in engine.models]

	def start_model_loading(
		self, account: config.Account, engine: BaseEngine, on_loaded: Callable
	) -> None:
		"""Spawn a background thread to load models and call on_loaded when done.

		Args:
			account: The account whose models to load.
			engine: The engine to load models from.
			on_loaded: Callback invoked on the UI thread with
				(account_id, models, error_message).
		"""
		generation = self._model_loading_generation
		cancel_event = threading.Event()
		self._model_loading_cancel_event = cancel_event
		self._model_loading_thread = threading.Thread(
			target=self._load_models_in_background,
			args=(account.id, engine, generation, cancel_event, on_loaded),
			name=f"model-loader-{account.id}",
			daemon=True,
		)
		self._model_loading_thread.start()

	def _load_models_in_background(
		self,
		account_id,
		engine: BaseEngine,
		generation: int,
		cancel_event: threading.Event,
		on_loaded: Callable,
	) -> None:
		"""Worker: load models and marshal result back to the UI thread."""
		error_message: str | None = None
		try:
			models = list(engine.models)
			error_message = engine.get_model_loading_error()
			if error_message and not models:
				engine.invalidate_models_cache()
		except Exception:
			log.exception("Failed to load models for account %s", account_id)
			error_message = _(
				"Failed to load models. Please check your network and account settings."
			)
			models = []
		if cancel_event.is_set():
			return
		if generation != self._model_loading_generation:
			return
		on_loaded(account_id, models, error_message)

	def shutdown_model_loading(self) -> None:
		"""Cancel and invalidate any in-flight model loading worker."""
		self._model_loading_generation += 1
		cancel_event = self._model_loading_cancel_event
		if cancel_event:
			cancel_event.set()
		self._model_loading_thread = None
		self._model_loading_cancel_event = None

	def set_pending_model(self, model_id: str, account_id: UUID) -> None:
		"""Store a deferred model selection to be applied once models load.

		Args:
			model_id: The model ID to select.
			account_id: The account ID the selection belongs to.
		"""
		self._pending_model_id = model_id
		self._pending_model_account_id = account_id

	def pop_pending_model(
		self, displayed_models: list[ProviderAIModel], account_id: UUID
	) -> ProviderAIModel | None:
		"""Find and clear the pending model selection.

		Args:
			displayed_models: The currently displayed models.
			account_id: The current account ID.

		Returns:
			The matching model, or None if not found or account mismatch.
		"""
		if not self._pending_model_id or self._pending_model_account_id is None:
			return None
		if self._pending_model_account_id != account_id:
			return None
		model = next(
			(m for m in displayed_models if m.id == self._pending_model_id),
			None,
		)
		self._pending_model_id = None
		self._pending_model_account_id = None
		return model

	def resolve_account_and_model(
		self,
		profile: config.ConversationProfile,
		fall_back_default_account: bool = False,
	) -> tuple[config.Account | None, str | None]:
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
