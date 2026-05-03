"""Tests for reasoning-capable loading configuration across providers."""

from functools import cached_property
from typing import Any
from unittest.mock import MagicMock

import pytest

from basilisk.conversation import Conversation, Message, MessageBlock
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_engine import base_engine
from basilisk.provider_engine.anthropic_engine import AnthropicEngine
from basilisk.provider_engine.deepseek_engine import DeepSeekAIEngine
from basilisk.provider_engine.dynamic_model_loader import (
	CATALOG_SOURCE_SIGMA_NIGHT_MASTER,
	ProviderMetadata,
)
from basilisk.provider_engine.mistralai_engine import MistralAIEngine
from basilisk.provider_engine.openai_engine import OpenAIEngine
from basilisk.provider_engine.xai_engine import XAIEngine


class _GeminiSigmaNightCatalogStub(base_engine.BaseEngine):
	"""Same catalog URL as GeminiEngine without importing google-genai.

	On Windows ARM64, ``cryptography`` often has no usable wheel; importing
	``google.genai`` pulls that stack and breaks test collection.
	"""

	MODELS_JSON_URL = base_engine.sigma_night_data_file("google.json")

	@cached_property
	def client(self):
		return MagicMock()

	def prepare_message_request(self, message: Message) -> Any:
		raise NotImplementedError

	def prepare_message_response(self, response: Any) -> Message:
		raise NotImplementedError

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs: Any,
	) -> Any:
		raise NotImplementedError

	def completion_response_with_stream(
		self, stream: Any, **kwargs: Any
	) -> Any:
		raise NotImplementedError

	def completion_response_without_stream(
		self, response: Any, new_block: MessageBlock, **kwargs: Any
	) -> MessageBlock:
		raise NotImplementedError


_SIGMA_NIGHT_CATALOG_ENGINES = [
	OpenAIEngine,
	DeepSeekAIEngine,
	XAIEngine,
	MistralAIEngine,
	AnthropicEngine,
	_GeminiSigmaNightCatalogStub,
]


@pytest.mark.parametrize("engine_cls", _SIGMA_NIGHT_CATALOG_ENGINES)
def test_models_loader_uses_dynamic_loader(engine_cls, monkeypatch):
	"""Providers with dynamic metadata delegate model loading to base loader."""
	acc = MagicMock()
	acc.api_key.get_secret_value.return_value = "sk-test"
	engine = engine_cls(acc)

	called_urls = []

	def _fake_loader(url: str):
		called_urls.append(url)
		return []

	monkeypatch.setattr(base_engine, "load_models_from_url", _fake_loader)
	discarded_models = engine.models
	assert discarded_models == []
	assert called_urls == [engine.MODELS_JSON_URL]


@pytest.mark.parametrize("engine_cls", _SIGMA_NIGHT_CATALOG_ENGINES)
def test_sigma_night_catalog_fetch_failure_returns_empty_models(
	engine_cls, monkeypatch
):
	"""Sigma-night catalog engines share BaseEngine cache; fetch failure is empty."""
	acc = MagicMock()
	acc.api_key.get_secret_value.return_value = "sk-test"
	engine = engine_cls(acc)

	def _boom_loader(_url: str):
		raise RuntimeError("network down")

	monkeypatch.setattr(base_engine, "load_models_from_url", _boom_loader)
	assert engine.models == []
	assert engine.get_model_loading_error() == "network down"


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

	monkeypatch.setattr(base_engine, "load_models_from_url", _fake_loader)
	out = engine.models
	assert called_urls == [engine.MODELS_JSON_URL]
	assert len(out) == 2
	assert out[0].reasoning is False
	assert out[1].reasoning is True


def test_loader_maps_reasoning_from_metadata_by_default():
	"""Reasoning flag is mapped from metadata without extra loader options."""
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
	for m in out:
		assert (
			m.extra_info["metadata_catalog"]
			== CATALOG_SOURCE_SIGMA_NIGHT_MASTER
		)


def test_loader_mapping_does_not_force_reasoning_from_id():
	"""ID naming alone does not enable reasoning when metadata says no."""
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
	assert (
		out[0].extra_info["metadata_catalog"]
		== CATALOG_SOURCE_SIGMA_NIGHT_MASTER
	)
