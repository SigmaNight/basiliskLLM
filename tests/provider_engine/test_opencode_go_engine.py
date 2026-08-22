"""Tests for the OpenCode and OpenCode Zen provider engines."""

from unittest.mock import MagicMock

import httpx
import pytest
from google.genai.types import ResourceScope
from pydantic import SecretStr

from basilisk.provider import ProviderAPIType, get_provider
from basilisk.provider_engine.opencode_go_engine import (
	OpenCodeGoEngine,
	OpenCodeZenEngine,
	_Protocol,
	_ProtocolResponse,
)

_LIVE_GO_MODEL_PROTOCOLS = (
	("minimax-m3", _Protocol.ANTHROPIC_MESSAGES),
	("minimax-m2.7", _Protocol.ANTHROPIC_MESSAGES),
	("minimax-m2.5", _Protocol.ANTHROPIC_MESSAGES),
	("kimi-k3", _Protocol.CHAT_COMPLETIONS),
	("kimi-k2.7-code", _Protocol.CHAT_COMPLETIONS),
	("kimi-k2.6", _Protocol.CHAT_COMPLETIONS),
	("kimi-k2.5", _Protocol.CHAT_COMPLETIONS),
	("glm-5.2", _Protocol.CHAT_COMPLETIONS),
	("glm-5.3", _Protocol.CHAT_COMPLETIONS),
	("ox-alpha-free", _Protocol.CHAT_COMPLETIONS),
	("glm-5.1", _Protocol.CHAT_COMPLETIONS),
	("glm-5", _Protocol.CHAT_COMPLETIONS),
	("deepseek-v4-pro", _Protocol.CHAT_COMPLETIONS),
	("deepseek-v4-flash", _Protocol.CHAT_COMPLETIONS),
	("deepseek-v4-flash-vision-exp", _Protocol.CHAT_COMPLETIONS),
	("qwen3.7-max", _Protocol.ANTHROPIC_MESSAGES),
	("qwen3.8-max", _Protocol.ANTHROPIC_MESSAGES),
	("qwen3.7-plus", _Protocol.ANTHROPIC_MESSAGES),
	("qwen3.6-plus", _Protocol.ANTHROPIC_MESSAGES),
	("qwen3.5-plus", _Protocol.CHAT_COMPLETIONS),
	("mimo-v2-pro", _Protocol.CHAT_COMPLETIONS),
	("mimo-v2-omni", _Protocol.CHAT_COMPLETIONS),
	("mimo-v2.5-pro", _Protocol.CHAT_COMPLETIONS),
	("mimo-v2.5", _Protocol.CHAT_COMPLETIONS),
	("hy3", _Protocol.CHAT_COMPLETIONS),
	("hy3-preview", _Protocol.CHAT_COMPLETIONS),
	("gpt-5.6-luna", _Protocol.RESPONSES),
	("grok-4.5", _Protocol.RESPONSES),
	("muse-spark-1.2-contributor", _Protocol.RESPONSES),
)
_LIVE_GO_MODEL_VISION = (
	("minimax-m3", False),
	("minimax-m2.7", False),
	("minimax-m2.5", False),
	("kimi-k3", True),
	("kimi-k2.7-code", True),
	("kimi-k2.6", True),
	("kimi-k2.5", True),
	("glm-5.2", False),
	("glm-5.3", False),
	("ox-alpha-free", True),
	("glm-5.1", False),
	("glm-5", False),
	("deepseek-v4-pro", False),
	("deepseek-v4-flash", False),
	("deepseek-v4-flash-vision-exp", True),
	("qwen3.7-max", False),
	("qwen3.8-max", True),
	("qwen3.7-plus", True),
	("qwen3.6-plus", True),
	("qwen3.5-plus", True),
	("mimo-v2-pro", True),
	("mimo-v2-omni", True),
	("mimo-v2.5-pro", True),
	("mimo-v2.5", True),
	("hy3", False),
	("hy3-preview", False),
	("gpt-5.6-luna", True),
	("grok-4.5", True),
	("muse-spark-1.2-contributor", True),
)


def _make_engine(engine_cls, provider_id):
	account = MagicMock()
	account.id = "account-test"
	account.provider = get_provider(id=provider_id)
	account.api_key = SecretStr("sk-test")
	account.custom_base_url = None
	return engine_cls(account)


@pytest.mark.parametrize(
	("provider_id", "name", "base_url", "engine_cls"),
	[
		(
			"opencodego",
			"OpenCode Go",
			"https://opencode.ai/zen/go/v1",
			OpenCodeGoEngine,
		),
		(
			"opencodezen",
			"OpenCode Zen",
			"https://opencode.ai/zen/v1",
			OpenCodeZenEngine,
		),
	],
)
def test_provider_registration(provider_id, name, base_url, engine_cls):
	"""Both account options expose their intended configuration."""
	provider = get_provider(id=provider_id)

	assert provider.name == name
	assert provider.base_url == base_url
	assert provider.api_type == ProviderAPIType.OPENAI
	assert provider.env_var_name_api_key == "OPENCODE_API_KEY"
	assert provider.engine_cls is engine_cls


@pytest.mark.parametrize(
	("engine_cls", "provider_id", "models_url", "expected_kimi_extra_info"),
	[
		(
			OpenCodeGoEngine,
			"opencodego",
			"https://opencode.ai/zen/go/v1/models",
			{
				"owned_by": "opencode",
				"unsupported_parameters": ["temperature", "top_p"],
			},
		),
		(
			OpenCodeZenEngine,
			"opencodezen",
			"https://opencode.ai/zen/v1/models",
			{"owned_by": "opencode"},
		),
	],
)
def test_model_discovery(
	httpx_mock, engine_cls, provider_id, models_url, expected_kimi_extra_info
):
	"""Each product discovers models from its own endpoint."""
	httpx_mock.add_response(
		url=models_url,
		json={
			"data": [
				{"id": "qwen3.7-plus", "created": 123, "owned_by": "opencode"},
				{"id": "kimi-k3", "created": 124, "owned_by": "opencode"},
				{"id": "text-model", "created": "invalid"},
				{"created": 456},
				"invalid",
			]
		},
	)
	engine = _make_engine(engine_cls, provider_id)

	models = engine._load_models()

	assert [model.id for model in models] == [
		"qwen3.7-plus",
		"kimi-k3",
		"text-model",
	]
	assert models[0].vision is True
	assert models[0].created == 123
	assert models[0].extra_info == {"owned_by": "opencode"}
	assert models[1].extra_info == expected_kimi_extra_info
	assert models[2].created == 0
	request = httpx_mock.get_requests()[0]
	assert request.headers["Authorization"] == "Bearer sk-test"


def test_model_discovery_rejects_non_list(httpx_mock):
	"""Malformed model payloads report a clear error."""
	httpx_mock.add_response(
		url="https://opencode.ai/zen/v1/models", json={"data": {}}
	)
	engine = _make_engine(OpenCodeZenEngine, "opencodezen")

	with pytest.raises(ValueError, match="invalid model list"):
		engine._load_models()


def test_model_discovery_http_error(httpx_mock):
	"""Model-list HTTP failures preserve status and response details."""
	httpx_mock.add_response(
		url="https://opencode.ai/zen/go/v1/models",
		status_code=401,
		text="invalid key",
	)
	engine = _make_engine(OpenCodeGoEngine, "opencodego")

	with pytest.raises(httpx.HTTPStatusError, match="status=401.*invalid key"):
		engine._load_models()


@pytest.mark.parametrize(("model_id", "protocol"), _LIVE_GO_MODEL_PROTOCOLS)
def test_live_go_models_use_audited_protocol(model_id, protocol):
	"""Every live Go model uses its audited transport."""
	engine = _make_engine(OpenCodeGoEngine, "opencodego")

	assert engine._protocol_for_model(model_id) == protocol


def test_unknown_go_model_uses_chat_completions():
	"""Future Go models retain the documented conservative fallback."""
	engine = _make_engine(OpenCodeGoEngine, "opencodego")

	assert (
		engine._protocol_for_model("future-model") == _Protocol.CHAT_COMPLETIONS
	)


@pytest.mark.parametrize(
	("model_id", "protocol"),
	[
		("gemini-3.7-flash", _Protocol.GEMINI),
		("claude-sonnet-5", _Protocol.ANTHROPIC_MESSAGES),
		("gpt-5.6-sol", _Protocol.RESPONSES),
		("deepseek-v4-pro", _Protocol.CHAT_COMPLETIONS),
	],
)
def test_zen_protocol_selection_is_unchanged(model_id, protocol):
	"""The Go audit does not alter Zen routing."""
	engine = _make_engine(OpenCodeZenEngine, "opencodezen")

	assert engine._protocol_for_model(model_id) == protocol


@pytest.mark.parametrize(("model_id", "vision"), _LIVE_GO_MODEL_VISION)
def test_live_go_models_use_audited_vision_metadata(model_id, vision):
	"""Every audited live Go model has its catalogued attachment support."""
	engine = _make_engine(OpenCodeGoEngine, "opencodego")

	assert (model_id in engine.VISION_MODELS) is vision


@pytest.mark.parametrize(
	("protocol", "adapter_name"),
	[
		(_Protocol.RESPONSES, "_responses_engine"),
		(_Protocol.ANTHROPIC_MESSAGES, "_anthropic_engine"),
		(_Protocol.GEMINI, "_gemini_engine"),
	],
)
def test_completion_routes_to_adapter(mocker, protocol, adapter_name):
	"""Completion creation delegates to the selected protocol adapter."""
	engine = _make_engine(OpenCodeZenEngine, "opencodezen")
	adapter = MagicMock()
	adapter.completion.return_value = "raw-response"
	engine.__dict__[adapter_name] = adapter
	mocker.patch.object(engine, "_protocol_for_model", return_value=protocol)
	new_block = MagicMock()
	new_block.model.model_id = "model-test"
	conversation = MagicMock()

	response = engine.completion(
		new_block, conversation, None, stop_block_index=2, extra="value"
	)

	assert response == _ProtocolResponse(protocol, "raw-response")
	adapter.completion.assert_called_once_with(
		new_block, conversation, None, 2, extra="value"
	)


@pytest.mark.parametrize(
	("protocol", "adapter_name"),
	[
		(_Protocol.RESPONSES, "_responses_engine"),
		(_Protocol.ANTHROPIC_MESSAGES, "_anthropic_engine"),
		(_Protocol.GEMINI, "_gemini_engine"),
	],
)
def test_response_processing_routes_to_adapter(protocol, adapter_name):
	"""Streaming and complete responses use the selected adapter."""
	engine = _make_engine(OpenCodeZenEngine, "opencodezen")
	adapter = MagicMock()
	adapter.completion_response_with_stream.return_value = iter(["chunk"])
	completed_block = MagicMock()
	adapter.completion_response_without_stream.return_value = completed_block
	engine.__dict__[adapter_name] = adapter
	response = _ProtocolResponse(protocol, "raw-response")
	new_block = MagicMock()

	assert list(engine.completion_response_with_stream(response)) == ["chunk"]
	assert (
		engine.completion_response_without_stream(response, new_block)
		is completed_block
	)
	adapter.completion_response_with_stream.assert_called_once_with(
		"raw-response"
	)
	adapter.completion_response_without_stream.assert_called_once_with(
		"raw-response", new_block
	)


@pytest.mark.parametrize(
	"model_id", ["kimi-k2.5", "kimi-k2.6", "kimi-k2.7-code", "kimi-k3"]
)
def test_go_kimi_models_use_fixed_sampling_parameters(
	httpx_mock, mocker, model_id
):
	"""Go Kimi chat requests override stored sampling values."""
	engine = _make_engine(OpenCodeGoEngine, "opencodego")
	httpx_mock.add_response(
		url="https://opencode.ai/zen/go/v1/models",
		json={"data": [{"id": model_id}]},
	)
	model = engine._load_models()[0]
	assert model.extra_info["unsupported_parameters"] == [
		"temperature",
		"top_p",
	]
	client = MagicMock()
	mocker.patch.object(engine, "get_model", return_value=model)
	mocker.patch.object(engine, "get_messages", return_value=[])
	mocker.patch.object(engine, "client", client)
	new_block = MagicMock()
	new_block.model.model_id = model_id
	new_block.stream = False
	new_block.temperature = 0.7
	new_block.top_p = 0.8
	new_block.max_tokens = 100

	engine.completion(new_block, MagicMock(), None)

	params = client.chat.completions.create.call_args.kwargs
	assert params["temperature"] == 1.0
	assert params["top_p"] == 0.95


def test_go_luna_responses_request_omits_sampling_parameters(
	httpx_mock, mocker
):
	"""GPT-5.6 Luna omits unsupported Responses sampling parameters."""
	engine = _make_engine(OpenCodeGoEngine, "opencodego")
	httpx_mock.add_response(
		url="https://opencode.ai/zen/go/v1/models",
		json={"data": [{"id": "gpt-5.6-luna"}]},
	)
	model = engine._load_models()[0]
	assert model.extra_info["unsupported_parameters"] == [
		"temperature",
		"top_p",
	]
	adapter = engine._responses_engine
	client = MagicMock()
	mocker.patch.object(adapter, "get_model", return_value=model)
	mocker.patch.object(adapter, "get_messages", return_value=[])
	mocker.patch.object(adapter, "client", client)
	new_block = MagicMock()
	new_block.model.model_id = model.id
	new_block.stream = False
	new_block.temperature = 0.7
	new_block.top_p = 0.8
	new_block.max_tokens = 100

	engine.completion(new_block, MagicMock(), None)

	params = client.responses.create.call_args.kwargs
	assert "temperature" not in params
	assert "top_p" not in params


def test_ordinary_go_chat_model_keeps_user_sampling_parameters(
	httpx_mock, mocker
):
	"""Go models without a policy retain the user's selected sampling values."""
	engine = _make_engine(OpenCodeGoEngine, "opencodego")
	httpx_mock.add_response(
		url="https://opencode.ai/zen/go/v1/models",
		json={"data": [{"id": "text-model"}]},
	)
	model = engine._load_models()[0]
	client = MagicMock()
	mocker.patch.object(engine, "get_model", return_value=model)
	mocker.patch.object(engine, "get_messages", return_value=[])
	mocker.patch.object(engine, "client", client)
	new_block = MagicMock()
	new_block.model.model_id = model.id
	new_block.stream = False
	new_block.temperature = 0.7
	new_block.top_p = 0.8
	new_block.max_tokens = 100

	engine.completion(new_block, MagicMock(), None)

	params = client.chat.completions.create.call_args.kwargs
	assert params["temperature"] == 0.7
	assert params["top_p"] == 0.8


def test_go_sampling_policy_does_not_apply_to_zen(httpx_mock, mocker):
	"""Zen Kimi requests retain their selected sampling values."""
	engine = _make_engine(OpenCodeZenEngine, "opencodezen")
	httpx_mock.add_response(
		url="https://opencode.ai/zen/v1/models",
		json={"data": [{"id": "kimi-k3"}]},
	)
	model = engine._load_models()[0]
	client = MagicMock()
	mocker.patch.object(engine, "get_model", return_value=model)
	mocker.patch.object(engine, "get_messages", return_value=[])
	mocker.patch.object(engine, "client", client)
	new_block = MagicMock()
	new_block.model.model_id = model.id
	new_block.stream = False
	new_block.temperature = 0.7
	new_block.top_p = 0.8
	new_block.max_tokens = 100

	engine.completion(new_block, MagicMock(), None)

	params = client.chat.completions.create.call_args.kwargs
	assert params["temperature"] == 0.7
	assert params["top_p"] == 0.8


def test_protocol_client_base_urls():
	"""All protocol clients target the OpenCode Zen gateway."""
	engine = _make_engine(OpenCodeZenEngine, "opencodezen")

	assert str(engine.client.base_url) == "https://opencode.ai/zen/v1/"
	assert str(engine._responses_engine.client.base_url) == (
		"https://opencode.ai/zen/v1/"
	)
	assert str(engine._anthropic_engine.client.base_url) == (
		"https://opencode.ai/zen/"
	)
	assert (
		engine._gemini_engine.client._api_client._http_options.base_url
		== "https://opencode.ai/zen/v1"
	)
	assert (
		engine._gemini_engine.client._api_client._http_options.base_url_resource_scope
		== ResourceScope.COLLECTION
	)


@pytest.mark.parametrize(
	("engine_cls", "provider_id"),
	[(OpenCodeGoEngine, "opencodego"), (OpenCodeZenEngine, "opencodezen")],
)
@pytest.mark.parametrize(
	"protocol",
	[
		_Protocol.CHAT_COMPLETIONS,
		_Protocol.RESPONSES,
		_Protocol.ANTHROPIC_MESSAGES,
	],
)
def test_cancel_closes_go_and_zen_streams(engine_cls, provider_id, protocol):
	"""Go and Zen close OpenAI-compatible and Anthropic SDK streams."""
	engine = _make_engine(engine_cls, provider_id)
	stream = MagicMock()

	engine.cancel_completion(_ProtocolResponse(protocol, stream))

	stream.close.assert_called_once_with()


def test_cancel_zen_gemini_stream_closes_and_recreates_client():
	"""Zen cancels Gemini's generator by closing its active HTTP client."""
	engine = _make_engine(OpenCodeZenEngine, "opencodezen")
	stream = MagicMock()
	stream.close.side_effect = ValueError("generator already executing")
	client = MagicMock()
	engine._gemini_engine.__dict__["client"] = client

	engine.cancel_completion(_ProtocolResponse(_Protocol.GEMINI, stream))

	stream.close.assert_called_once_with()
	client.close.assert_called_once_with()
	assert "client" not in engine._gemini_engine.__dict__
