"""Tests for the OpenCode and OpenCode Zen provider engines."""

from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import SecretStr

from basilisk.provider import ProviderAPIType, get_provider
from basilisk.provider_engine.opencode_go_engine import (
	OpenCodeGoEngine,
	OpenCodeZenEngine,
	_Protocol,
	_ProtocolResponse,
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
			"OpenCode",
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
	("engine_cls", "provider_id", "models_url"),
	[
		(
			OpenCodeGoEngine,
			"opencodego",
			"https://opencode.ai/zen/go/v1/models",
		),
		(OpenCodeZenEngine, "opencodezen", "https://opencode.ai/zen/v1/models"),
	],
)
def test_model_discovery(httpx_mock, engine_cls, provider_id, models_url):
	"""Each product discovers models from its own endpoint."""
	httpx_mock.add_response(
		url=models_url,
		json={
			"data": [
				{"id": "qwen3.7-plus", "created": 123, "owned_by": "opencode"},
				{"id": "text-model", "created": "invalid"},
				{"created": 456},
				"invalid",
			]
		},
	)
	engine = _make_engine(engine_cls, provider_id)

	models = engine._load_models()

	assert [model.id for model in models] == ["qwen3.7-plus", "text-model"]
	assert models[0].vision is True
	assert models[0].created == 123
	assert models[0].extra_info == {"owned_by": "opencode"}
	assert models[1].created == 0
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


@pytest.mark.parametrize(
	("engine_cls", "provider_id", "model_id", "protocol"),
	[
		(OpenCodeGoEngine, "opencodego", "gpt-5.6-luna", _Protocol.RESPONSES),
		(
			OpenCodeGoEngine,
			"opencodego",
			"minimax-m3",
			_Protocol.ANTHROPIC_MESSAGES,
		),
		(OpenCodeGoEngine, "opencodego", "kimi-k3", _Protocol.CHAT_COMPLETIONS),
		(
			OpenCodeZenEngine,
			"opencodezen",
			"gemini-3.7-flash",
			_Protocol.GEMINI,
		),
		(
			OpenCodeZenEngine,
			"opencodezen",
			"claude-sonnet-5",
			_Protocol.ANTHROPIC_MESSAGES,
		),
		(OpenCodeZenEngine, "opencodezen", "gpt-5.6-sol", _Protocol.RESPONSES),
		(
			OpenCodeZenEngine,
			"opencodezen",
			"deepseek-v4-pro",
			_Protocol.CHAT_COMPLETIONS,
		),
	],
)
def test_protocol_selection(engine_cls, provider_id, model_id, protocol):
	"""Models route through the protocol documented for each product."""
	engine = _make_engine(engine_cls, provider_id)

	assert engine._protocol_for_model(model_id) == protocol


@pytest.mark.parametrize(
	("protocol", "adapter_name"),
	[
		(_Protocol.RESPONSES, "_responses_engine"),
		(_Protocol.ANTHROPIC_MESSAGES, "_anthropic_engine"),
		(_Protocol.GEMINI, "_gemini_engine"),
	],
)
def test_completion_routes_to_adapter(protocol, adapter_name):
	"""Completion creation delegates to the selected protocol adapter."""
	engine = _make_engine(OpenCodeZenEngine, "opencodezen")
	adapter = MagicMock()
	adapter.completion.return_value = "raw-response"
	engine.__dict__[adapter_name] = adapter
	engine._protocol_for_model = MagicMock(return_value=protocol)
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
