"""Tests for OpenRouter reasoning UI spec and completion params.

Per OpenRouter docs (https://openrouter.ai/docs/guides/best-practices/reasoning-tokens):
- Anthropic/Gemini/Alibaba: reasoning.max_tokens (no adaptive)
- OpenAI/Grok: reasoning.effort (minimal/low/medium/high/xhigh)
"""

from unittest.mock import MagicMock

import pytest

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.provider_ai_model import AIModelInfo, ProviderAIModel
from basilisk.provider_engine.openrouter_engine import (
	OpenRouterEngine,
	_openrouter_reasoning_provider,
)


@pytest.fixture
def mock_openrouter_account():
	"""Mock account for OpenRouter."""
	account = MagicMock()
	account.api_key.get_secret_value.return_value = "test-key"
	account.provider.id = "openrouter"
	account.custom_base_url = None
	account.provider.base_url = "https://openrouter.ai/api/v1"
	return account


@pytest.fixture
def empty_conversation():
	"""Empty conversation for tests."""
	return Conversation(messages=[])


def test_openrouter_reasoning_provider_extraction():
	"""Extract provider from OpenRouter model ID."""
	assert (
		_openrouter_reasoning_provider("anthropic/claude-sonnet-4-6")
		== "anthropic"
	)
	assert _openrouter_reasoning_provider("openai/gpt-4o") == "openai"
	assert _openrouter_reasoning_provider("google/gemini-2.5-flash") == "google"
	assert _openrouter_reasoning_provider("x-ai/grok-3-mini") == "x-ai"
	assert _openrouter_reasoning_provider("deepseek/deepseek-r1") == "deepseek"
	assert (
		_openrouter_reasoning_provider("alibaba/qwen3-235b-a22b") == "alibaba"
	)
	assert _openrouter_reasoning_provider("") is None
	assert _openrouter_reasoning_provider("no-slash") is None


def test_openrouter_anthropic_no_adaptive(mock_openrouter_account):
	"""OpenRouter with Anthropic Claude: budget only, no adaptive (API does not support it)."""
	engine = OpenRouterEngine(account=mock_openrouter_account)
	model = ProviderAIModel(
		id="anthropic/claude-sonnet-4-6",
		name="Claude Sonnet 4.6",
		context_window=200000,
		max_output_tokens=64000,
		reasoning=False,
		reasoning_capable=True,
		supported_parameters=["reasoning"],
	)
	spec = engine.get_reasoning_ui_spec(model)
	assert spec.show is True
	assert spec.show_adaptive is False
	assert spec.show_budget is True
	assert spec.show_effort is False
	assert spec.budget_default == 16000
	assert spec.budget_max == 128000


def test_openrouter_openai_effort_options(mock_openrouter_account):
	"""OpenRouter with OpenAI: effort dropdown includes xhigh per docs."""
	engine = OpenRouterEngine(account=mock_openrouter_account)
	model = ProviderAIModel(
		id="openai/gpt-4o",
		name="GPT-4o",
		context_window=128000,
		max_output_tokens=4096,
		reasoning=False,
		reasoning_capable=True,
		supported_parameters=["reasoning"],
	)
	spec = engine.get_reasoning_ui_spec(model)
	assert spec.show is True
	assert spec.show_adaptive is False
	assert spec.show_budget is False
	assert spec.show_effort is True
	assert spec.effort_options == ("minimal", "low", "medium", "high", "xhigh")


def test_openrouter_budget_provider_sends_max_tokens(
	mock_openrouter_account, empty_conversation, mocker
):
	"""OpenRouter with Anthropic: reasoning.max_tokens in extra_body."""
	model = ProviderAIModel(
		id="anthropic/claude-sonnet-4-6",
		name="Claude Sonnet 4.6",
		context_window=200000,
		max_output_tokens=64000,
		reasoning=False,
		reasoning_capable=True,
		supported_parameters=["reasoning"],
	)
	engine = OpenRouterEngine(account=mock_openrouter_account)
	mocker.patch.object(engine, "get_model", return_value=model)
	mocker.patch.object(engine, "client", MagicMock())
	engine.client.chat.completions.create = MagicMock(
		return_value=MagicMock(
			choices=[
				MagicMock(message=MagicMock(content="Hi", reasoning=None))
			],
			usage=MagicMock(),
		)
	)

	block = MessageBlock(
		request=Message(role=MessageRoleEnum.USER, content="Hello"),
		model=AIModelInfo(
			provider_id="openrouter", model_id="anthropic/claude-sonnet-4-6"
		),
		temperature=0.7,
		max_tokens=4096,
		stream=False,
		reasoning_mode=True,
		reasoning_budget_tokens=8000,
	)

	engine.completion(block, empty_conversation, None, None)

	call_kwargs = engine.client.chat.completions.create.call_args[1]
	assert "extra_body" in call_kwargs
	assert call_kwargs["extra_body"]["reasoning"] == {"max_tokens": 8000}


def test_openrouter_effort_provider_sends_effort(
	mock_openrouter_account, empty_conversation, mocker
):
	"""OpenRouter with OpenAI: reasoning.effort in extra_body."""
	model = ProviderAIModel(
		id="openai/gpt-4o",
		name="GPT-4o",
		context_window=128000,
		max_output_tokens=4096,
		reasoning=False,
		reasoning_capable=True,
		supported_parameters=["reasoning"],
	)
	engine = OpenRouterEngine(account=mock_openrouter_account)
	mocker.patch.object(engine, "get_model", return_value=model)
	mocker.patch.object(engine, "client", MagicMock())
	engine.client.chat.completions.create = MagicMock(
		return_value=MagicMock(
			choices=[
				MagicMock(message=MagicMock(content="Hi", reasoning=None))
			],
			usage=MagicMock(),
		)
	)

	block = MessageBlock(
		request=Message(role=MessageRoleEnum.USER, content="Hello"),
		model=AIModelInfo(provider_id="openrouter", model_id="openai/gpt-4o"),
		temperature=0.7,
		max_tokens=4096,
		stream=False,
		reasoning_mode=True,
		reasoning_effort="high",
	)

	engine.completion(block, empty_conversation, None, None)

	call_kwargs = engine.client.chat.completions.create.call_args[1]
	assert call_kwargs["extra_body"]["reasoning"] == {"effort": "high"}


def test_openrouter_effort_invalid_falls_back_to_medium(
	mock_openrouter_account, empty_conversation, mocker
):
	"""Invalid effort value falls back to medium. Uses model_construct to bypass Pydantic validation (e.g. legacy DB data)."""
	model = ProviderAIModel(
		id="openai/gpt-4o",
		name="GPT-4o",
		context_window=128000,
		max_output_tokens=4096,
		reasoning=False,
		reasoning_capable=True,
		supported_parameters=["reasoning"],
	)
	engine = OpenRouterEngine(account=mock_openrouter_account)
	mocker.patch.object(engine, "get_model", return_value=model)
	mocker.patch.object(engine, "client", MagicMock())
	engine.client.chat.completions.create = MagicMock(
		return_value=MagicMock(
			choices=[
				MagicMock(message=MagicMock(content="Hi", reasoning=None))
			],
			usage=MagicMock(),
		)
	)

	block = MessageBlock.model_construct(
		request=Message(role=MessageRoleEnum.USER, content="Hello"),
		model=AIModelInfo(provider_id="openrouter", model_id="openai/gpt-4o"),
		temperature=0.7,
		max_tokens=4096,
		stream=False,
		reasoning_mode=True,
		reasoning_effort="invalid_value",
	)

	engine.completion(block, empty_conversation, None, None)

	call_kwargs = engine.client.chat.completions.create.call_args[1]
	assert call_kwargs["extra_body"]["reasoning"] == {"effort": "medium"}


def test_openrouter_no_reasoning_when_mode_off(
	mock_openrouter_account, empty_conversation, mocker
):
	"""When reasoning_mode=False, no reasoning in extra_body."""
	model = ProviderAIModel(
		id="anthropic/claude-sonnet-4-6",
		name="Claude Sonnet 4.6",
		context_window=200000,
		max_output_tokens=64000,
		reasoning=False,
		reasoning_capable=True,
		supported_parameters=["reasoning"],
	)
	engine = OpenRouterEngine(account=mock_openrouter_account)
	mocker.patch.object(engine, "get_model", return_value=model)
	mocker.patch.object(engine, "client", MagicMock())
	engine.client.chat.completions.create = MagicMock(
		return_value=MagicMock(
			choices=[
				MagicMock(message=MagicMock(content="Hi", reasoning=None))
			],
			usage=MagicMock(),
		)
	)

	block = MessageBlock(
		request=Message(role=MessageRoleEnum.USER, content="Hello"),
		model=AIModelInfo(
			provider_id="openrouter", model_id="anthropic/claude-sonnet-4-6"
		),
		temperature=0.7,
		max_tokens=4096,
		stream=False,
		reasoning_mode=False,
	)

	engine.completion(block, empty_conversation, None, None)

	call_kwargs = engine.client.chat.completions.create.call_args[1]
	assert "reasoning" not in (call_kwargs.get("extra_body") or {})
