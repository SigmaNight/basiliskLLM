"""Tests for OpenRouter model loading behavior."""

from unittest.mock import MagicMock

import httpx
import pytest

from basilisk.provider_engine.openrouter_engine import OpenRouterEngine


def _make_engine(monkeypatch, tmp_path) -> OpenRouterEngine:
	monkeypatch.setattr(
		"basilisk.provider_engine.model_cache_registry.global_vars.user_data_path",
		tmp_path,
	)
	account = MagicMock()
	account.id = "acct-test"
	account.custom_base_url = None
	account.provider.id = "prov-test"
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


def test_models_sorted_by_created_desc(httpx_mock, monkeypatch, tmp_path):
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
	engine = _make_engine(monkeypatch, tmp_path)
	models = engine.models
	assert [model.id for model in models] == ["newer", "middle", "older"]
	assert [model.created for model in models] == [3000, 2000, 1000]


def test_models_invalid_created_falls_back_to_zero(
	httpx_mock, monkeypatch, tmp_path
):
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
	engine = _make_engine(monkeypatch, tmp_path)
	models = engine.models
	assert [model.id for model in models] == [
		"valid-created",
		"invalid-created",
	]
	assert [model.created for model in models] == [42, 0]


def test_models_non_200_response_raises(httpx_mock, monkeypatch, tmp_path):
	"""Non-200 model discovery responses should propagate as errors."""
	httpx_mock.add_response(
		status_code=503,
		text="upstream unavailable",
		url="https://openrouter.ai/api/v1/models",
	)
	engine = _make_engine(monkeypatch, tmp_path)
	with pytest.raises(
		httpx.HTTPStatusError, match="status=503.*upstream unavailable"
	):
		engine._load_models()
