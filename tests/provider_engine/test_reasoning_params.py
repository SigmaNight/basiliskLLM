"""Tests for reasoning mode param injection in engines."""

from unittest.mock import MagicMock

import pytest

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.provider_ai_model import AIModelInfo, ProviderAIModel
from basilisk.provider_engine.anthropic_engine import AnthropicEngine


@pytest.fixture
def mock_account():
	"""Mock account with API key."""
	account = MagicMock()
	account.api_key.get_secret_value.return_value = "test-key"
	account.provider.id = "anthropic"
	account.custom_base_url = None
	return account


@pytest.fixture
def reasoning_capable_model():
	"""Model that supports optional reasoning via param."""
	return ProviderAIModel(
		id="claude-sonnet-4-6",
		name="Claude Sonnet 4.6",
		context_window=200000,
		max_output_tokens=64000,
		reasoning=False,
		reasoning_capable=True,
		supported_parameters=["temperature", "max_tokens", "include_reasoning"],
	)


@pytest.fixture
def message_block_with_reasoning(reasoning_capable_model):
	"""MessageBlock with reasoning_mode enabled."""
	return MessageBlock(
		request=Message(role=MessageRoleEnum.USER, content="Test"),
		model=AIModelInfo(
			provider_id="anthropic", model_id="claude-sonnet-4-6"
		),
		temperature=0.7,
		max_tokens=4096,
		stream=False,
		reasoning_mode=True,
		reasoning_budget_tokens=16000,
		reasoning_adaptive=False,
	)


@pytest.fixture
def empty_conversation():
	"""Empty conversation for completion context."""
	return Conversation(messages=[])


def test_anthropic_reasoning_mode_adds_thinking_param(
	mock_account,
	reasoning_capable_model,
	message_block_with_reasoning,
	empty_conversation,
	mocker,
):
	"""When reasoning_mode=True and model is reasoning_capable, thinking param is added."""
	engine = AnthropicEngine(account=mock_account)
	mock_client = MagicMock()
	engine.client = mock_client
	mocker.patch.object(
		engine, "get_model", return_value=reasoning_capable_model
	)
	mock_create = mock_client.messages.create
	mock_create.return_value = MagicMock(
		content=[MagicMock(content=[MagicMock(text="")])],
		id="msg-1",
		model="claude-sonnet-4-6",
		role="assistant",
		stop_reason="end_turn",
	)

	engine.completion(
		message_block_with_reasoning, empty_conversation, None, None
	)

	mock_create.assert_called_once()
	call_kwargs = mock_create.call_args[1]
	assert "thinking" in call_kwargs
	assert call_kwargs["thinking"] == {
		"type": "enabled",
		"budget_tokens": 16000,
	}
	assert "top_p" not in call_kwargs


def test_anthropic_reasoning_adaptive_adds_adaptive_thinking(
	mock_account, empty_conversation, mocker
):
	"""When reasoning_adaptive=True and model supports it, thinking type is adaptive."""
	# Model ID must contain "4.6" for _supports_adaptive (per anthropic_engine)
	adaptive_model = ProviderAIModel(
		id="claude-sonnet-4.6",
		name="Claude Sonnet 4.6",
		context_window=200000,
		max_output_tokens=64000,
		reasoning=False,
		reasoning_capable=True,
		supported_parameters=["temperature", "max_tokens", "include_reasoning"],
	)
	engine = AnthropicEngine(account=mock_account)
	mock_client = MagicMock()
	engine.client = mock_client
	mocker.patch.object(engine, "get_model", return_value=adaptive_model)
	mock_create = mock_client.messages.create
	mock_create.return_value = MagicMock(
		content=[MagicMock(content=[MagicMock(text="")])],
		id="msg-1",
		model="claude-sonnet-4.6",
		role="assistant",
		stop_reason="end_turn",
	)

	block = MessageBlock(
		request=Message(role=MessageRoleEnum.USER, content="Test"),
		model=AIModelInfo(
			provider_id="anthropic", model_id="claude-sonnet-4.6"
		),
		temperature=0.7,
		max_tokens=4096,
		stream=False,
		reasoning_mode=True,
		reasoning_adaptive=True,
	)

	engine.completion(block, empty_conversation, None, None)

	call_kwargs = mock_create.call_args[1]
	assert call_kwargs["thinking"] == {"type": "adaptive"}
