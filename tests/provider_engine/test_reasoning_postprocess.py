"""Tests for reasoning-capable loading configuration across providers."""

from unittest.mock import MagicMock

import pytest

import basilisk.provider_engine.base_engine as _base_engine
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_engine.anthropic_engine import AnthropicEngine
from basilisk.provider_engine.deepseek_engine import DeepSeekAIEngine
from basilisk.provider_engine.openai_engine import OpenAIEngine
from basilisk.provider_engine.xai_engine import XAIEngine


@pytest.mark.parametrize(
	"engine_cls", [OpenAIEngine, DeepSeekAIEngine, XAIEngine]
)
def test_models_loader_uses_dynamic_loader(engine_cls, monkeypatch):
	"""Providers with dynamic metadata delegate model loading to base loader."""
	acc = MagicMock()
	acc.api_key.get_secret_value.return_value = "sk-test"
	engine = engine_cls(acc)

	called_urls = []

	def _fake_loader(url: str):
		called_urls.append(url)
		return []

	monkeypatch.setattr(_base_engine, "load_models_from_url", _fake_loader)
	discarded_models = engine.models
	assert discarded_models == []
	assert called_urls == [engine.MODELS_JSON_URL]


def test_anthropic_loader_synthesizes_thinking_variants(monkeypatch):
	"""Anthropic keeps base rows non-reasoning to synthesize thinking variants."""
	acc = MagicMock()
	acc.api_key.get_secret_value.return_value = "sk-test"
	engine = AnthropicEngine(acc)

	called_urls = []

	def _fake_loader(url: str):
		called_urls.append(url)
		return [
			ProviderAIModel(
				id="claude-sonnet-4-6",
				name="Claude Sonnet 4.6",
				extra_info={"reasoning_capable": True},
			)
		]

	monkeypatch.setattr(_base_engine, "load_models_from_url", _fake_loader)
	out = engine.models
	assert called_urls == [engine.MODELS_JSON_URL]
	assert len(out) == 2
	assert out[0].reasoning is False
	assert out[1].reasoning is True


def test_loader_maps_reasoning_from_metadata_by_default():
	"""Reasoning flag is mapped from metadata without extra loader options."""
	from basilisk.provider_engine.dynamic_model_loader import ProviderMetadata

	raw = {
		"models": [
			{
				"id": "m1",
				"top_provider": {"context_length": 1},
				"supported_parameters": ["reasoning"],
			},
			{
				"id": "m2",
				"top_provider": {"context_length": 1},
				"supported_parameters": ["temperature"],
			},
		]
	}
	out = ProviderMetadata.model_validate(raw).get_provider_models()
	assert [m.reasoning for m in out] == [True, False]


def test_loader_mapping_does_not_force_reasoning_from_id():
	"""ID naming alone does not enable reasoning when metadata says no."""
	from basilisk.provider_engine.dynamic_model_loader import ProviderMetadata

	raw = {
		"models": [
			{
				"id": "o3",
				"top_provider": {"context_length": 1},
				"supported_parameters": ["temperature"],
			}
		]
	}
	out = ProviderMetadata.model_validate(raw).get_provider_models()
	assert len(out) == 1
	assert out[0].reasoning is False
