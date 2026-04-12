"""Tests for dynamic model loader."""

import httpx
import pytest

import basilisk.provider_engine.dynamic_model_loader as _dml
from basilisk.provider_ai_model import ProviderAIModel

fetch_models_json = _dml.fetch_models_json
load_models_from_url = _dml.load_models_from_url

_EXTRA_INFO_KEYS = frozenset(k.value for k in _dml.ModelExtraInfoKey)


def parse_model_metadata(raw: dict) -> list[ProviderAIModel]:
	"""Local test helper — wraps ProviderMetadata.model_validate for unit tests."""
	try:
		return _dml.ProviderMetadata.model_validate(raw).get_provider_models()
	except Exception:
		return []


@pytest.fixture(autouse=True)
def _clear_dynamic_model_cache():
	"""Isolate tests: module-level model cache must not leak between cases."""
	_dml._CACHE.clear()
	yield
	_dml._CACHE.clear()


def _models_by_id(raw: dict) -> dict[str, ProviderAIModel]:
	return {m.id: m for m in parse_model_metadata(raw)}


def _minimal_item(model_id: str, **extra) -> dict:
	row = {"id": model_id, "top_provider": {"context_length": 1}}
	row.update(extra)
	return row


@pytest.mark.parametrize(
	("raw", "expected_len"),
	[({}, 0), ({"models": []}, 0), ({"models": None}, 0)],
)
def test_parse_model_metadata_empty(raw, expected_len):
	"""parse_model_metadata returns empty list for empty or invalid models key."""
	assert len(parse_model_metadata(raw)) == expected_len


def test_parse_model_metadata_openai_structure():
	"""parse_model_metadata maps OpenAI-style JSON to ProviderAIModel."""
	raw = {
		"models": [
			{
				"id": "gpt-5.2",
				"name": "GPT-5.2",
				"description": "Best model",
				"architecture": {
					"input_modalities": ["text", "image"],
					"output_modalities": ["text"],
				},
				"top_provider": {
					"context_length": 400000,
					"max_completion_tokens": 128000,
				},
				"supported_parameters": [
					"include_reasoning",
					"max_tokens",
					"temperature",
				],
				"default_parameters": {"temperature": 0.7},
			}
		]
	}
	models = parse_model_metadata(raw)
	assert len(models) == 1
	m = models[0]
	assert m.id == "gpt-5.2"
	assert m.name == "GPT-5.2"
	assert m.description == "Best model"
	assert m.context_window == 400000
	assert m.max_output_tokens == 128000
	assert m.max_temperature == 2.0
	assert m.default_temperature == 0.7
	assert m.reasoning is True
	assert m.vision is True
	assert m.created == 0
	assert m.extra_info["reasoning_capable"] is True
	assert "include_reasoning" in m.extra_info["supported_parameters"]
	assert_extra_info_shape(m)


def assert_extra_info_shape(m: ProviderAIModel) -> None:
	"""Document the loader's extra_info contract."""
	assert set(m.extra_info.keys()) == _EXTRA_INFO_KEYS


def test_parse_model_metadata_extra_info_defaults():
	"""Minimal row yields expected extra_info defaults and vision-only flag."""
	raw = {"models": [_minimal_item("m")]}
	m = parse_model_metadata(raw)[0]
	assert_extra_info_shape(m)
	assert m.extra_info["supported_parameters"] == []
	assert m.extra_info["reasoning_capable"] is False
	assert m.extra_info["web_search_capable"] is False
	assert m.extra_info["audio_input"] is False
	assert m.extra_info["document_input"] is False
	assert m.extra_info["video_input"] is False
	assert m.extra_info["image_output"] is False
	assert m.extra_info["audio_output"] is False
	assert m.extra_info["video_output"] is False


def test_default_temperature_null_uses_standard_default():
	"""Null temperature in JSON keeps ProviderAIModel default (1.0)."""
	raw = {
		"models": [_minimal_item("t", default_parameters={"temperature": None})]
	}
	assert parse_model_metadata(raw)[0].default_temperature == 1.0


def test_default_temperature_numeric_from_json():
	"""Numeric default_parameters.temperature is copied to the model."""
	raw = {
		"models": [
			_minimal_item(
				"t", default_parameters={"temperature": 0.42, "top_p": 0.9}
			)
		]
	}
	assert parse_model_metadata(raw)[0].default_temperature == 0.42


def test_image_input_and_output_from_modality_arrays():
	"""image in both input and output arrays sets vision and image_output."""
	raw = {
		"models": [
			{
				"id": "gemini-image-out",
				"architecture": {
					"input_modalities": ["text", "image"],
					"output_modalities": ["text", "image"],
				},
			}
		]
	}
	m = parse_model_metadata(raw)[0]
	assert m.vision is True
	assert m.extra_info["image_output"] is True


def test_audio_input_and_output_from_modality_arrays():
	"""audio in both input and output arrays sets audio_input and audio_output."""
	raw = {
		"models": [
			{
				"id": "gpt-audio",
				"architecture": {
					"input_modalities": ["text", "audio"],
					"output_modalities": ["text", "audio"],
				},
			}
		]
	}
	m = parse_model_metadata(raw)[0]
	assert m.extra_info["audio_input"] is True
	assert m.extra_info["audio_output"] is True


def test_google_multimodal_inputs_from_modality_arrays():
	"""Google-style multimodal: many inputs, text-only output."""
	raw = {
		"models": [
			{
				"id": "gemini-pro",
				"architecture": {
					"input_modalities": [
						"text",
						"image",
						"file",
						"audio",
						"video",
					],
					"output_modalities": ["text"],
				},
			}
		]
	}
	m = parse_model_metadata(raw)[0]
	assert m.vision is True
	assert m.extra_info["document_input"] is True
	assert m.extra_info["audio_input"] is True
	assert m.extra_info["video_input"] is True
	assert m.extra_info["image_output"] is False


def test_parse_model_metadata_filters_models_without_text_output():
	"""Models with explicit non-text output only are excluded from Basilisk UI."""
	raw = {
		"models": [
			{
				"id": "image-only-model",
				"architecture": {"output_modalities": ["image"]},
			},
			{
				"id": "video-only-model",
				"architecture": {"output_modalities": ["video"]},
			},
			{
				"id": "text-model",
				"architecture": {"output_modalities": ["text"]},
			},
		]
	}
	assert [m.id for m in parse_model_metadata(raw)] == ["text-model"]


def test_parse_model_metadata_keeps_model_without_explicit_output_modalities():
	"""When output_modalities is absent, keep model for compatibility."""
	raw = {"models": [{"id": "legacy-model", "architecture": {}}]}
	assert [m.id for m in parse_model_metadata(raw)] == ["legacy-model"]


def test_parse_model_metadata_includes_all_models_from_json():
	"""parse_model_metadata includes all models; no ID-based filtering."""
	raw = {
		"models": [
			_minimal_item("claude-sonnet-4.6", name="Base"),
			{
				"id": "claude-3.7-sonnet:thinking",
				"name": "Thinking",
				"top_provider": {"context_length": 1000},
				"supported_parameters": ["reasoning", "include_reasoning"],
			},
			_minimal_item("claude-opus-4-6_reasoning", name="Reasoning"),
		]
	}
	by_id = _models_by_id(raw)
	assert set(by_id) == {
		"claude-sonnet-4.6",
		"claude-3.7-sonnet:thinking",
		"claude-opus-4-6_reasoning",
	}
	assert (
		by_id["claude-3.7-sonnet:thinking"].extra_info["reasoning_capable"]
		is True
	)


def test_parse_model_metadata_context_length_only_from_top_provider():
	"""parse_model_metadata uses top_provider for context_length and max_completion_tokens."""
	raw = {
		"models": [
			{
				"id": "test",
				"top_provider": {
					"context_length": 2000,
					"max_completion_tokens": 64000,
				},
			}
		]
	}
	m = parse_model_metadata(raw)[0]
	assert m.context_window == 2000
	assert m.max_output_tokens == 64000


def test_parse_model_metadata_vision_from_input_modalities():
	"""Vision flag set when image appears in input_modalities."""
	raw = {
		"models": [
			{
				"id": "with-vision",
				"architecture": {"input_modalities": ["text", "image"]},
			},
			{"id": "no-vision", "architecture": {"input_modalities": ["text"]}},
		]
	}
	by_id = _models_by_id(raw)
	assert by_id["with-vision"].vision is True
	assert by_id["no-vision"].vision is False


def test_parse_model_metadata_audio_from_modality_arrays():
	"""parse_model_metadata records audio in extra_info."""
	raw = {
		"models": [
			{
				"id": "with-audio",
				"architecture": {
					"input_modalities": ["text", "audio"],
					"output_modalities": ["text"],
				},
			},
			{
				"id": "no-audio",
				"architecture": {
					"input_modalities": ["text"],
					"output_modalities": ["text"],
				},
			},
		]
	}
	by_id = _models_by_id(raw)
	assert by_id["with-audio"].extra_info["audio_input"] is True
	assert by_id["no-audio"].extra_info["audio_input"] is False


def test_parse_model_metadata_document_from_input_modalities():
	"""Document/file input from input_modalities array."""
	raw = {
		"models": [
			{
				"id": "doc-arrays",
				"architecture": {
					"input_modalities": ["text", "file"],
					"output_modalities": ["text"],
				},
			},
			{
				"id": "no-doc",
				"architecture": {
					"input_modalities": ["text"],
					"output_modalities": ["text"],
				},
			},
		]
	}
	by_id = _models_by_id(raw)
	assert by_id["doc-arrays"].extra_info["document_input"] is True
	assert by_id["no-doc"].extra_info["document_input"] is False


def test_parse_model_metadata_audio_from_input_modalities():
	"""parse_model_metadata derives audio from input_modalities array."""
	raw = {
		"models": [
			{
				"id": "audio-via-input-modalities",
				"architecture": {
					"input_modalities": ["text", "audio"],
					"output_modalities": ["text"],
				},
			}
		]
	}
	assert (
		_models_by_id(raw)["audio-via-input-modalities"].extra_info[
			"audio_input"
		]
		is True
	)


def test_parse_model_metadata_reasoning_capable_from_supported_parameters():
	"""parse_model_metadata sets reasoning_capable in extra_info."""
	raw = {
		"models": [
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
	by_id = _models_by_id(raw)
	assert by_id["with-reasoning"].extra_info["reasoning_capable"] is True
	assert (
		by_id["with-include-reasoning"].extra_info["reasoning_capable"] is True
	)
	assert by_id["no-reasoning"].extra_info["reasoning_capable"] is False


def test_parse_model_metadata_image_output_from_output_modalities():
	"""parse_model_metadata sets image_output in extra_info."""
	raw = {
		"models": [
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
	by_id = _models_by_id(raw)
	assert by_id["image-gen"].extra_info["image_output"] is True
	assert by_id["text-only"].extra_info["image_output"] is False
	assert by_id["vision-model"].extra_info["image_output"] is False


def test_parse_model_metadata_audio_output_from_output_modalities():
	"""parse_model_metadata sets audio_output in extra_info."""
	raw = {
		"models": [
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
	by_id = _models_by_id(raw)
	assert by_id["gpt-audio"].extra_info["audio_output"] is True
	assert by_id["text-only"].extra_info["audio_output"] is False


def test_fetch_models_json_success(httpx_mock):
	"""fetch_models_json returns a ProviderMetadata on success."""
	httpx_mock.add_response(
		json={"models": [{"id": "gpt-5", "name": "GPT-5"}]},
		url="https://example.com/models.json",
	)
	result = fetch_models_json("https://example.com/models.json")
	assert result.models[0].id == "gpt-5"


def test_fetch_models_json_network_error(httpx_mock):
	"""fetch_models_json raises on HTTP error."""
	httpx_mock.add_response(
		status_code=500, url="https://example.com/models.json"
	)
	with pytest.raises(httpx.HTTPStatusError):
		fetch_models_json("https://example.com/models.json")


def test_parse_model_metadata_sorts_by_created_desc():
	"""parse_model_metadata sorts models by created descending (newest first)."""
	raw = {
		"models": [
			{"id": "old", "created": 1000},
			{"id": "new", "created": 3000},
			{"id": "mid", "created": 2000},
		]
	}
	assert [m.id for m in parse_model_metadata(raw)] == ["new", "mid", "old"]


def test_parse_model_metadata_sort_stable_equal_created():
	"""Equal created values preserve input order (stable sort)."""
	raw = {
		"models": [
			{
				"id": "first",
				"created": 5,
				"top_provider": {"context_length": 1},
			},
			{
				"id": "second",
				"created": 5,
				"top_provider": {"context_length": 1},
			},
			{
				"id": "older",
				"created": 1,
				"top_provider": {"context_length": 1},
			},
		]
	}
	assert [m.id for m in parse_model_metadata(raw)] == [
		"first",
		"second",
		"older",
	]


def test_load_models_from_url_success(httpx_mock):
	"""load_models_from_url fetches and parses models."""
	httpx_mock.add_response(
		json={
			"models": [
				{
					"id": "gpt-5",
					"name": "GPT-5",
					"top_provider": {
						"context_length": 400000,
						"max_completion_tokens": 128000,
					},
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
	assert load_models_from_url("https://example.com/nonexistent.json") == []


def test_parse_model_metadata_web_search_capable_from_json():
	"""parse_model_metadata sets web_search_capable in extra_info."""
	raw = {
		"models": [
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
	by_id = _models_by_id(raw)
	assert by_id["with-web-search"].extra_info["web_search_capable"] is True
	assert by_id["without-web-search"].extra_info["web_search_capable"] is False


def test_parse_model_metadata_web_search_capable_fallback_tools():
	"""parse_model_metadata uses tools in supported_parameters when supports_web_search absent."""
	raw = {
		"models": [
			{
				"id": "with-tools",
				"supported_parameters": ["tools", "max_tokens"],
			},
			{"id": "no-tools", "supported_parameters": ["temperature"]},
		]
	}
	by_id = _models_by_id(raw)
	assert by_id["with-tools"].extra_info["web_search_capable"] is True
	assert by_id["no-tools"].extra_info["web_search_capable"] is False


def test_parse_model_metadata_skips_entries_with_invalid_field_types():
	"""OnErrorOmit skips model entries whose fields fail Pydantic validation."""
	raw = {
		"models": [
			{"id": "null-top-provider", "top_provider": None},
			{
				"id": "invalid-max-tokens",
				"top_provider": {
					"context_length": 1000,
					"max_completion_tokens": [1, 2, 3],
				},
			},
			{
				"id": "invalid-created",
				"top_provider": {"context_length": 1000},
				"created": "invalid",
			},
			{"id": "valid", "top_provider": {"context_length": 1000}},
		]
	}
	models = parse_model_metadata(raw)
	assert [m.id for m in models] == ["valid"]


def test_parse_model_metadata_null_max_completion_tokens_uses_default():
	"""Null max_completion_tokens in JSON uses _DEFAULT_MAX_OUTPUT_TOKENS (-1)."""
	raw = {
		"models": [
			{
				"id": "t",
				"top_provider": {
					"context_length": 1000,
					"max_completion_tokens": None,
				},
			}
		]
	}
	assert parse_model_metadata(raw)[0].max_output_tokens == -1


def test_parse_model_metadata_skips_non_dict_entries_in_models_list():
	"""Non-dict elements in the models array are ignored."""
	raw = {"models": ["not-a-dict", 42, _minimal_item("ok")]}
	assert [m.id for m in parse_model_metadata(raw)] == ["ok"]


def test_parse_model_metadata_skips_item_with_non_string_or_empty_id():
	"""Items without a non-empty string id are skipped."""
	raw = {
		"models": [
			{"id": 123, "top_provider": {"context_length": 1}},
			{"id": "", "top_provider": {"context_length": 1}},
			{"top_provider": {"context_length": 1}},
		]
	}
	assert parse_model_metadata(raw) == []


def test_parse_model_metadata_skips_entry_with_non_list_supported_parameters():
	"""Non-list supported_parameters → ValidationError → OnErrorOmit → item skipped."""
	raw = {
		"models": [
			{
				"id": "m",
				"supported_parameters": "max_tokens",
				"top_provider": {"context_length": 1},
			}
		]
	}
	assert parse_model_metadata(raw) == []


def test_parse_model_metadata_skips_entry_with_non_dict_architecture():
	"""Non-dict architecture → ValidationError → OnErrorOmit → item skipped."""
	raw = {
		"models": [
			{
				"id": "m",
				"architecture": "oops",
				"top_provider": {"context_length": 1},
			}
		]
	}
	assert parse_model_metadata(raw) == []


def test_load_models_from_url_returns_cached_payload_without_second_fetch(
	httpx_mock,
):
	"""Second load within TTL does not trigger another HTTP request."""
	url = "https://example.com/only-one-fetch.json"
	httpx_mock.add_response(json={"models": [_minimal_item("first")]}, url=url)
	first = load_models_from_url(url)
	assert first[0].id == "first"
	second = load_models_from_url(url)
	assert second[0].id == "first"
	assert len(httpx_mock.get_requests()) == 1


def test_load_models_from_url_error_returns_cached_when_present(
	httpx_mock, monkeypatch
):
	"""On fetch failure, previously cached models are returned if available."""
	url = "https://example.com/stale-on-error.json"
	httpx_mock.add_response(json={"models": [_minimal_item("stale")]}, url=url)
	assert load_models_from_url(url)[0].id == "stale"
	httpx_mock.add_response(status_code=500, url=url)
	cached_models, _ = _dml._CACHE[url]
	_dml._CACHE[url] = (cached_models, 0.0)
	monkeypatch.setattr(_dml.time, "monotonic", lambda: 1e9)
	out = load_models_from_url(url)
	assert len(out) == 1
	assert out[0].id == "stale"


def test_load_models_from_url_unexpected_error_is_not_suppressed(monkeypatch):
	"""Unexpected internal errors should propagate instead of returning empty data."""
	valid_metadata = _dml.ProviderMetadata.model_validate(
		{"models": [_minimal_item("x")]}
	)
	monkeypatch.setattr(_dml, "fetch_models_json", lambda _url: valid_metadata)

	def _boom(self):
		raise RuntimeError("unexpected parser bug")

	monkeypatch.setattr(_dml.ProviderMetadata, "get_provider_models", _boom)
	with pytest.raises(RuntimeError, match="unexpected parser bug"):
		load_models_from_url("https://example.com/models.json")
