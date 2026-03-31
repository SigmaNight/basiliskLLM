"""Shared param keys and helpers for MessageBlock and ConversationProfile.

Keeps reasoning params in sync when copying between block and profile.
"""

from __future__ import annotations

import enum
from typing import Any


class ReasoningParamKey(enum.StrEnum):
	"""Field names shared by MessageBlock and ConversationProfile for reasoning."""

	REASONING_MODE = "reasoning_mode"
	REASONING_BUDGET_TOKENS = "reasoning_budget_tokens"
	REASONING_EFFORT = "reasoning_effort"
	REASONING_ADAPTIVE = "reasoning_adaptive"


REASONING_PARAM_KEYS: tuple[str, ...] = tuple(
	m.value for m in ReasoningParamKey
)


def get_reasoning_params_from_block(block: Any) -> dict[str, Any]:
	"""Extract reasoning params from a MessageBlock for profile sync.

	Args:
		block: MessageBlock (or object with same attributes).

	Returns:
		Dict with reasoning field names, values from block.
	"""
	return {k.value: getattr(block, k.value, None) for k in ReasoningParamKey}


def get_reasoning_params_from_profile(profile: Any) -> dict[str, Any]:
	"""Extract reasoning params from a ConversationProfile for block sync.

	Args:
		profile: ConversationProfile (or object with same attributes).

	Returns:
		Dict with reasoning field names, values from profile.
	"""
	return {k.value: getattr(profile, k.value, None) for k in ReasoningParamKey}
