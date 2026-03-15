"""Presenter providing account/model resolution logic for conversation views.

Extracts the pure, testable parts of BaseConversation into a wx-free
presenter that can be shared between ConversationTab and any future
conversation panel.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import basilisk.config as config
from basilisk.services.account_model_service import AccountModelService

if TYPE_CHECKING:
	from basilisk.provider_ai_model import ProviderAIModel
	from basilisk.provider_engine.base_engine import BaseEngine

log = logging.getLogger(__name__)


@dataclass
class ParameterVisibilityState:
	"""Visibility state for parameter controls. View applies this to widgets."""

	temperature_visible: bool = False
	top_p_visible: bool = False
	max_tokens_visible: bool = False
	stream_visible: bool = False
	web_search_visible: bool = False
	reasoning_mode_visible: bool = False
	reasoning_adaptive_visible: bool = False
	reasoning_budget_visible: bool = False
	reasoning_effort_visible: bool = False
	effort_options: tuple[str, ...] = ()
	effort_display: tuple[str, ...] = ()
	effort_label: str = ""


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

	def get_parameter_visibility_state(
		self,
		advanced_mode: bool,
		model: ProviderAIModel | None,
		engine: BaseEngine | None,
		reasoning_mode_checked: bool = False,
		reasoning_adaptive_checked: bool = False,
	) -> ParameterVisibilityState:
		"""Compute visibility state for parameter controls.

		Business logic for which controls to show based on model, engine,
		and provider. View applies result to widgets.

		Args:
			advanced_mode: Whether advanced mode is enabled.
			model: Current model, or None.
			engine: Current engine, or None.
			reasoning_mode_checked: Current value of reasoning_mode checkbox.
			reasoning_adaptive_checked: Current value of reasoning_adaptive.

		Returns:
			ParameterVisibilityState to apply to view widgets.
		"""
		state = ParameterVisibilityState()
		if model is None or engine is None:
			return state

		has_model = advanced_mode and model is not None
		state.temperature_visible = has_model and model.supports_parameter(
			"temperature"
		)
		state.top_p_visible = has_model and model.supports_parameter("top_p")
		state.max_tokens_visible = has_model and model.supports_parameter(
			"max_tokens"
		)
		state.stream_visible = has_model

		state.web_search_visible = engine.model_supports_web_search(model)

		# Delegate to engine for reasoning visibility—no provider_id checks
		reasoning_spec = engine.get_reasoning_ui_spec(model)
		state.reasoning_mode_visible = reasoning_spec.show

		controls_visible = (
			reasoning_spec.show
			and reasoning_mode_checked
			and engine is not None
		)
		state.reasoning_adaptive_visible = (
			controls_visible and reasoning_spec.show_adaptive
		)
		state.reasoning_budget_visible = (
			controls_visible
			and reasoning_spec.show_budget
			and not reasoning_adaptive_checked
		)
		state.reasoning_effort_visible = (
			controls_visible and reasoning_spec.show_effort
		)
		state.effort_options = reasoning_spec.effort_options
		state.effort_label = reasoning_spec.effort_label
		state.effort_display = tuple(
			s.capitalize() for s in reasoning_spec.effort_options
		)

		return state
