"""Tests for provider reasoning / Anthropic stream StrEnums."""

import pytest

from basilisk.provider_engine.reasoning_api_enums import (
	AnthropicReasoningEffort,
	GeminiThinkingEffortKey,
	OpenRouterReasoningEffort,
)


@pytest.mark.parametrize(
	("raw", "expected"),
	[
		(None, OpenRouterReasoningEffort.MEDIUM),
		("HIGH", OpenRouterReasoningEffort.HIGH),
		("xhigh", OpenRouterReasoningEffort.XHIGH),
		("not-a-real-effort", OpenRouterReasoningEffort.MEDIUM),
	],
)
def test_openrouter_reasoning_effort_normalize(raw, expected):
	"""Unknown strings fall back to medium."""
	assert OpenRouterReasoningEffort.normalize(raw) is expected


@pytest.mark.parametrize(
	("effort", "ok"),
	[("low", True), ("MAX", True), ("minimal", False), ("xhigh", False)],
)
def test_anthropic_reasoning_effort_valid(effort, ok):
	"""Only low/medium/high/max are accepted for adaptive output_config."""
	assert AnthropicReasoningEffort.is_valid(effort) is ok


def test_gemini_thinking_effort_key_values():
	"""Gemini 3 effort keys are the expected wire strings."""
	assert GeminiThinkingEffortKey.HIGH == "high"
