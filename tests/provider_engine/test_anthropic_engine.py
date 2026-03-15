"""Tests for Anthropic engine model post-processing and responses."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_engine.anthropic_engine import (
	_REASONING_ID_SUFFIX,
	AnthropicEngine,
)


@pytest.fixture
def anthropic_engine() -> AnthropicEngine:
	"""Minimal AnthropicEngine for unit tests (no network)."""
	acc = MagicMock()
	acc.api_key.get_secret_value.return_value = "sk-test"
	return AnthropicEngine(acc)


def test_postprocess_adds_thinking_variant_for_claude4_opus_sonnet_haiku(
	anthropic_engine: AnthropicEngine,
):
	"""Reasoning-capable models get a synthetic ``*_reasoning`` row."""
	base = ProviderAIModel(
		id="claude-sonnet-4-6",
		name="Claude Sonnet 4.6",
		context_window=200_000,
		max_output_tokens=64_000,
		extra_info={"reasoning_capable": True},
	)
	out = anthropic_engine._postprocess_models([base])
	assert len(out) == 2
	assert out[0].id == "claude-sonnet-4-6"
	assert out[0].reasoning is False
	assert out[1].id == "claude-sonnet-4-6" + _REASONING_ID_SUFFIX
	assert out[1].reasoning is True
	assert out[1].name == "Claude Sonnet 4.6 (thinking)"


def test_postprocess_no_thinking_variant_for_claude_3_5(
	anthropic_engine: AnthropicEngine,
):
	"""Non-reasoning-capable models do not get synthetic thinking variants."""
	m = ProviderAIModel(
		id="claude-3-5-sonnet-latest", name="Claude 3.5 Sonnet", extra_info={}
	)
	out = anthropic_engine._postprocess_models([m])
	assert len(out) == 1
	assert out[0].reasoning is False


def test_postprocess_adds_thinking_variant_when_reasoning_capable(
	anthropic_engine: AnthropicEngine,
):
	"""Reasoning-capable flag drives thinking variant creation regardless of ID family."""
	m = ProviderAIModel(
		id="claude-3-5-sonnet-latest",
		name="Claude 3.5 Sonnet",
		extra_info={"reasoning_capable": True},
	)
	out = anthropic_engine._postprocess_models([m])
	assert len(out) == 2
	assert out[1].id == "claude-3-5-sonnet-latest" + _REASONING_ID_SUFFIX
	assert out[1].reasoning is True


def test_postprocess_skips_twin_when_json_already_has_reasoning_id(
	anthropic_engine: AnthropicEngine,
):
	"""Do not synthesize ``*_reasoning`` if that id already exists in the feed."""
	base = ProviderAIModel(
		id="claude-opus-4-6",
		name="Claude Opus 4.6",
		extra_info={"reasoning_capable": True},
	)
	existing = ProviderAIModel(
		id="claude-opus-4-6" + _REASONING_ID_SUFFIX,
		name="Claude Opus 4.6 (thinking)",
		reasoning=True,
		extra_info={},
	)
	out = anthropic_engine._postprocess_models([base, existing])
	ids = [m.id for m in out]
	assert ids.count("claude-opus-4-6" + _REASONING_ID_SUFFIX) == 1


def test_completion_response_without_stream_renders_thinking_block(
	anthropic_engine: AnthropicEngine,
):
	"""Thinking blocks are rendered into a ```think fenced section."""
	response = SimpleNamespace(
		thinking=None,
		content=[
			SimpleNamespace(type="thinking", thinking="step 1", citations=None),
			SimpleNamespace(type="text", text="final answer", citations=None),
		],
	)
	new_block = SimpleNamespace(response=None)
	anthropic_engine.completion_response_without_stream(response, new_block)
	assert "```think\nstep 1\n```" in new_block.response.content
	assert new_block.response.content.endswith("final answer")


def test_completion_response_without_stream_uses_legacy_response_thinking(
	anthropic_engine: AnthropicEngine,
):
	"""Legacy response.thinking is still rendered when present."""
	response = SimpleNamespace(
		thinking="legacy thoughts",
		content=[SimpleNamespace(type="text", text="result", citations=None)],
	)
	new_block = SimpleNamespace(response=None)
	anthropic_engine.completion_response_without_stream(response, new_block)
	assert "```think\nlegacy thoughts\n```" in new_block.response.content
	assert new_block.response.content.endswith("result")
