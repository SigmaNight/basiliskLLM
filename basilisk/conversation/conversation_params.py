"""Shared param keys and helpers for MessageBlock and ConversationProfile.

Keeps reasoning params in sync when copying between block and profile.
"""

from __future__ import annotations

from typing import Any

# Keys shared by MessageBlock and ConversationProfile for reasoning mode.
REASONING_PARAM_KEYS: tuple[str, ...] = (
	"reasoning_mode",
	"reasoning_budget_tokens",
	"reasoning_effort",
	"reasoning_adaptive",
)


def get_reasoning_params_from_block(block: Any) -> dict[str, Any]:
	"""Extract reasoning params from a MessageBlock for profile sync.

	Args:
		block: MessageBlock (or object with same attributes).

	Returns:
		Dict with REASONING_PARAM_KEYS, values from block.
	"""
	return {k: getattr(block, k, None) for k in REASONING_PARAM_KEYS}


def get_reasoning_params_from_profile(profile: Any) -> dict[str, Any]:
	"""Extract reasoning params from a ConversationProfile for block sync.

	Args:
		profile: ConversationProfile (or object with same attributes).

	Returns:
		Dict with REASONING_PARAM_KEYS, values from profile.
	"""
	return {k: getattr(profile, k, None) for k in REASONING_PARAM_KEYS}
