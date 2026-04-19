"""Tests for OpenRouter model loading behavior."""

from unittest.mock import MagicMock

from basilisk.provider_engine.openrouter_engine import OpenRouterEngine


def _make_engine() -> OpenRouterEngine:
	account = MagicMock()
	account.api_key.get_secret_value.return_value = "sk-test"
	return OpenRouterEngine(account)


def _model_row(model_id: str, created=0) -> dict:
	return {
		"id": model_id,
		"name": model_id.upper(),
		"description": f"{model_id} description",
		"context_length": 128000,
		"created": created,
		"top_provider": {"max_completion_tokens": 4096},
		"architecture": {"modality": "text->text"},
	}


def test_models_sorted_by_created_desc(httpx_mock):
	"""OpenRouter model list is sorted by created timestamp descending."""
	httpx_mock.add_response(
		json={
			"data": [
				_model_row("older", created=1000),
				_model_row("newer", created=3000),
				_model_row("middle", created=2000),
			]
		},
		url="https://openrouter.ai/api/v1/models",
	)
	engine = _make_engine()
	models = engine.models
	assert [model.id for model in models] == ["newer", "middle", "older"]
	assert [model.created for model in models] == [3000, 2000, 1000]


def test_models_invalid_created_falls_back_to_zero(httpx_mock):
	"""Invalid created values are normalized to 0 instead of crashing."""
	httpx_mock.add_response(
		json={
			"data": [
				_model_row("valid-created", created=42),
				_model_row("invalid-created", created="not-a-number"),
			]
		},
		url="https://openrouter.ai/api/v1/models",
	)
	engine = _make_engine()
	models = engine.models
	assert [model.id for model in models] == [
		"valid-created",
		"invalid-created",
	]
	assert [model.created for model in models] == [42, 0]
