"""Tests for conversation_params helpers."""

from types import SimpleNamespace

from basilisk.conversation.conversation_params import (
	REASONING_PARAM_KEYS,
	ReasoningParamKey,
	get_reasoning_params_from_block,
)


def test_reasoning_param_keys_match_enum():
	"""REASONING_PARAM_KEYS stays a value-for-value mirror of ReasoningParamKey."""
	assert REASONING_PARAM_KEYS == tuple(m.value for m in ReasoningParamKey)


def test_get_reasoning_params_from_block():
	"""get_reasoning_params_from_block maps block attributes to a dict."""
	block = SimpleNamespace(
		reasoning_mode=True,
		reasoning_budget_tokens=8000,
		reasoning_effort="high",
		reasoning_adaptive=False,
	)
	got = get_reasoning_params_from_block(block)
	assert got["reasoning_mode"] is True
	assert got["reasoning_budget_tokens"] == 8000
	assert got["reasoning_effort"] == "high"
	assert got["reasoning_adaptive"] is False
