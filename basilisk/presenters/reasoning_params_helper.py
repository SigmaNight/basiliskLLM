"""Helper for extracting reasoning parameters from conversation views.

Shared logic used by ConversationPresenter, EditBlockPresenter, and
EditConversationProfilePresenter to avoid duplication.
"""

from __future__ import annotations

from typing import Any

from basilisk.provider_engine.reasoning_config import get_effort_options


def get_reasoning_params_from_view(
	view: Any, provider_id: str = "", model_id: str = ""
) -> dict[str, Any]:
	"""Extract reasoning params from view widgets for MessageBlock/ConversationProfile.

	Args:
		view: View with reasoning_mode, reasoning_adaptive, reasoning_budget_spin,
			reasoning_effort_choice widgets (or subset).
		provider_id: Provider ID for effort options (fallback if view has no account).
		model_id: Model ID for effort options (fallback if view has no model).

	Returns:
		Dict with keys: reasoning_mode, reasoning_budget_tokens, reasoning_effort,
		reasoning_adaptive. Safe to pass as MessageBlock kwargs.
	"""
	result: dict[str, Any] = {
		"reasoning_mode": False,
		"reasoning_budget_tokens": None,
		"reasoning_effort": None,
		"reasoning_adaptive": False,
	}
	if not hasattr(view, "reasoning_mode") or not view.reasoning_mode.IsShown():
		return result

	val = view.reasoning_mode.GetValue()
	result["reasoning_mode"] = bool(val) if isinstance(val, bool) else False

	if hasattr(view, "reasoning_adaptive"):
		val = view.reasoning_adaptive.GetValue()
		result["reasoning_adaptive"] = (
			bool(val) if isinstance(val, bool) else False
		)

	if hasattr(view, "reasoning_budget_spin"):
		val = view.reasoning_budget_spin.GetValue()
		result["reasoning_budget_tokens"] = (
			val if isinstance(val, int) else None
		)

	if hasattr(view, "reasoning_effort_choice"):
		pid = (
			view.current_account.provider.id
			if view.current_account
			else provider_id
		)
		mid = view.current_model.id if view.current_model else model_id
		options = get_effort_options(pid, mid)
		effort_idx = view.reasoning_effort_choice.GetSelection()
		if isinstance(effort_idx, int) and 0 <= effort_idx < len(options):
			result["reasoning_effort"] = options[effort_idx]
		elif options:
			result["reasoning_effort"] = options[-1]

	return result
