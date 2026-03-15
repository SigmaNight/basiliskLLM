"""Tests for dynamic model loader."""

import pytest

from basilisk.provider_engine.dynamic_model_loader import (
	fetch_models_json,
	load_models_from_url,
	parse_model_metadata,
)


def test_parse_model_metadata_empty():
	"""parse_model_metadata returns empty list for empty or invalid input."""
	assert parse_model_metadata({}) == []
	assert parse_model_metadata({"data": []}) == []
	assert parse_model_metadata({"data": None}) == []


def test_parse_model_metadata_openai_structure():
	"""parse_model_metadata maps OpenAI-style JSON to ProviderAIModel."""
	raw = {
		"data": [
			{
				"id": "gpt-5.2",
				"name": "GPT-5.2",
				"description": "Best model",
				"context_length": 400000,
				"architecture": {"modality": "text+image->text"},
				"top_provider": {
					"context_length": 400000,
					"max_completion_tokens": 128000,
				},
				"supported_parameters": [
					"include_reasoning",
					"max_tokens",
					"temperature",
				],
			}
		]
	}
	models = parse_model_metadata(raw)
	assert len(models) == 1
	m = models[0]
	assert m.id == "gpt-5.2"
	assert m.name == "GPT-5.2"
	assert m.context_window == 400000
	assert m.max_output_tokens == 128000
	assert m.vision is True
	assert m.reasoning_capable is True
	assert "include_reasoning" in m.supported_parameters


def test_parse_model_metadata_includes_all_models_from_json():
	"""parse_model_metadata includes all models; no ID-based filtering.

	Reasoning support comes from supported_parameters. Each engine handles
	provider-specific logic (e.g. :thinking variants) in _postprocess_models.
	"""
	raw = {
		"data": [
			{"id": "claude-sonnet-4.6", "name": "Base", "context_length": 1000},
			{
				"id": "claude-3.7-sonnet:thinking",
				"name": "Thinking",
				"context_length": 1000,
				"supported_parameters": ["reasoning", "include_reasoning"],
			},
			{
				"id": "claude-opus-4-6_reasoning",
				"name": "Reasoning",
				"context_length": 1000,
			},
		]
	}
	models = parse_model_metadata(raw)
	ids = [m.id for m in models]
	assert "claude-sonnet-4.6" in ids
	assert "claude-3.7-sonnet:thinking" in ids
	assert "claude-opus-4-6_reasoning" in ids
	# reasoning_capable from JSON supported_parameters
	by_id = {m.id: m for m in models}
	assert by_id["claude-3.7-sonnet:thinking"].reasoning_capable is True


def test_parse_model_metadata_top_provider_overrides_root():
	"""parse_model_metadata uses top_provider for context_length and max_completion_tokens."""
	raw = {
		"data": [
			{
				"id": "test",
				"context_length": 1000,
				"top_provider": {
					"context_length": 2000,
					"max_completion_tokens": 64000,
				},
			}
		]
	}
	models = parse_model_metadata(raw)
	assert len(models) == 1
	assert models[0].context_window == 2000
	assert models[0].max_output_tokens == 64000


def test_parse_model_metadata_vision_from_modality():
	"""parse_model_metadata derives vision from architecture.modality."""
	raw = {
		"data": [
			{
				"id": "with-vision",
				"architecture": {"modality": "text+image->text"},
			},
			{"id": "no-vision", "architecture": {"modality": "text->text"}},
		]
	}
	models = parse_model_metadata(raw)
	by_id = {m.id: m for m in models}
	assert by_id["with-vision"].vision is True
	assert by_id["no-vision"].vision is False


def test_parse_model_metadata_audio_from_modality():
	"""parse_model_metadata derives audio from architecture.modality."""
	raw = {
		"data": [
			{
				"id": "with-audio",
				"architecture": {"modality": "text+audio->text"},
			},
			{"id": "no-audio", "architecture": {"modality": "text->text"}},
		]
	}
	models = parse_model_metadata(raw)
	by_id = {m.id: m for m in models}
	assert by_id["with-audio"].audio is True
	assert by_id["no-audio"].audio is False


def test_parse_model_metadata_audio_from_input_modalities():
	"""parse_model_metadata derives audio from input_modalities when modality lacks it."""
	raw = {
		"data": [
			{
				"id": "audio-via-input-modalities",
				"architecture": {
					"modality": "text->text",
					"input_modalities": ["text", "audio"],
				},
			}
		]
	}
	models = parse_model_metadata(raw)
	by_id = {m.id: m for m in models}
	assert by_id["audio-via-input-modalities"].audio is True


def test_parse_model_metadata_reasoning_capable_from_supported_parameters():
	"""parse_model_metadata sets reasoning_capable when reasoning in supported_parameters."""
	raw = {
		"data": [
			{
				"id": "with-reasoning",
				"supported_parameters": ["reasoning", "max_tokens"],
			},
			{
				"id": "with-include-reasoning",
				"supported_parameters": ["include_reasoning"],
			},
			{
				"id": "no-reasoning",
				"supported_parameters": ["temperature", "max_tokens"],
			},
		]
	}
	models = parse_model_metadata(raw)
	by_id = {m.id: m for m in models}
	assert by_id["with-reasoning"].reasoning_capable is True
	assert by_id["with-include-reasoning"].reasoning_capable is True
	assert by_id["no-reasoning"].reasoning_capable is False


def test_parse_model_metadata_image_output_from_output_modalities():
	"""parse_model_metadata sets image_output only when output_modalities contains image."""
	raw = {
		"data": [
			{
				"id": "image-gen",
				"architecture": {"output_modalities": ["image", "text"]},
			},
			{
				"id": "text-only",
				"architecture": {"output_modalities": ["text"]},
			},
			{
				"id": "vision-model",
				"architecture": {
					"modality": "text+image->text",
					"output_modalities": ["text"],
				},
			},
		]
	}
	models = parse_model_metadata(raw)
	by_id = {m.id: m for m in models}
	assert by_id["image-gen"].image_output is True
	assert by_id["text-only"].image_output is False
	assert by_id["vision-model"].image_output is False


def test_parse_model_metadata_audio_output_from_output_modalities():
	"""parse_model_metadata sets audio_output only when output_modalities contains audio."""
	raw = {
		"data": [
			{
				"id": "gpt-audio",
				"architecture": {"output_modalities": ["text", "audio"]},
			},
			{
				"id": "text-only",
				"architecture": {"output_modalities": ["text"]},
			},
		]
	}
	models = parse_model_metadata(raw)
	by_id = {m.id: m for m in models}
	assert by_id["gpt-audio"].audio_output is True
	assert by_id["text-only"].audio_output is False


def test_fetch_models_json_success(httpx_mock):
	"""fetch_models_json returns parsed JSON on success."""
	httpx_mock.add_response(
		json={"data": [{"id": "gpt-5", "name": "GPT-5"}]},
		url="https://example.com/models.json",
	)
	result = fetch_models_json("https://example.com/models.json")
	assert result["data"][0]["id"] == "gpt-5"


def test_fetch_models_json_network_error(httpx_mock):
	"""fetch_models_json raises on HTTP error."""
	httpx_mock.add_response(
		status_code=500, url="https://example.com/models.json"
	)
	import httpx

	with pytest.raises(httpx.HTTPStatusError):
		fetch_models_json("https://example.com/models.json")


def test_parse_model_metadata_sorts_by_created_desc():
	"""parse_model_metadata sorts models by created descending (newest first)."""
	raw = {
		"data": [
			{"id": "old", "created": 1000},
			{"id": "new", "created": 3000},
			{"id": "mid", "created": 2000},
		]
	}
	models = parse_model_metadata(raw)
	assert [m.id for m in models] == ["new", "mid", "old"]


def test_load_models_from_url_success(httpx_mock):
	"""load_models_from_url fetches and parses models."""
	httpx_mock.add_response(
		json={
			"data": [
				{
					"id": "gpt-5",
					"name": "GPT-5",
					"context_length": 400000,
					"top_provider": {"max_completion_tokens": 128000},
				}
			]
		},
		url="https://example.com/models.json",
	)
	models = load_models_from_url("https://example.com/models.json")
	assert len(models) == 1
	assert models[0].id == "gpt-5"


def test_load_models_from_url_network_error_returns_empty(httpx_mock):
	"""load_models_from_url returns empty list on fetch error when no cache."""
	httpx_mock.add_response(
		status_code=404, url="https://example.com/nonexistent.json"
	)
	models = load_models_from_url("https://example.com/nonexistent.json")
	assert models == []


def test_parse_model_metadata_web_search_capable_from_json():
	"""parse_model_metadata sets web_search_capable from supports_web_search."""
	raw = {
		"data": [
			{
				"id": "with-web-search",
				"supports_web_search": True,
				"supported_parameters": [],
			},
			{
				"id": "without-web-search",
				"supports_web_search": False,
				"supported_parameters": ["tools"],
			},
		]
	}
	models = parse_model_metadata(raw)
	by_id = {m.id: m for m in models}
	assert by_id["with-web-search"].web_search_capable is True
	assert by_id["without-web-search"].web_search_capable is False


def test_parse_model_metadata_web_search_capable_fallback_tools():
	"""parse_model_metadata uses tools in supported_parameters when supports_web_search absent."""
	raw = {
		"data": [
			{
				"id": "with-tools",
				"supported_parameters": ["tools", "max_tokens"],
			},
			{"id": "no-tools", "supported_parameters": ["temperature"]},
		]
	}
	models = parse_model_metadata(raw)
	by_id = {m.id: m for m in models}
	assert by_id["with-tools"].web_search_capable is True
	assert by_id["no-tools"].web_search_capable is False
