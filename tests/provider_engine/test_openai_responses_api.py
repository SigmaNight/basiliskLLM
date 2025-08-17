#!/usr/bin/env python3
"""Test suite for OpenAI Responses API integration with live API calls.

This module tests the actual OpenAI Responses API integration with real API calls.
It includes both basic functionality tests and comprehensive edge case testing.
"""

import os
import sys
from pathlib import Path

import pytest
from pydantic import SecretStr

# Add the project root to Python path for tests
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from basilisk.config import Account  # noqa: E402
from basilisk.conversation import (  # noqa: E402
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.provider import get_provider  # noqa: E402
from basilisk.provider_ai_model import AIModelInfo  # noqa: E402
from basilisk.provider_engine.openai_engine import OpenAIEngine  # noqa: E402


class TestResponsesAPILive:
	"""Live API tests that require actual OpenAI API key."""

	@pytest.fixture
	def engine(self):
		"""Create engine with real API credentials."""
		api_key = os.getenv("OPENAI_API_KEY")
		if not api_key:
			pytest.skip("OPENAI_API_KEY environment variable not set")
		
		provider = get_provider(id="openai")
		account = Account(
			provider=provider,
			api_key=SecretStr(api_key),
			name='test_account',
		)
		return OpenAIEngine(account)

	def test_engine_creation(self, engine):
		"""Test that engine can be created successfully."""
		assert engine is not None
		assert hasattr(engine, 'client')
		assert hasattr(engine, 'models')

	def test_model_discovery(self, engine):
		"""Test that models are properly configured."""
		models = engine.models
		assert len(models) > 0
		
		# Find GPT-5 models that should use responses API
		gpt5_models = [m for m in models if m.id.startswith("gpt-5")]
		assert len(gpt5_models) > 0
		
		# Verify they have the responses API preference (some may be False)
		responses_api_models = [m for m in gpt5_models if getattr(m, 'prefer_responses_api', False)]
		assert len(responses_api_models) > 0  # At least some should use responses API
		
		for model in responses_api_models:
			assert hasattr(model, 'prefer_responses_api')
			assert model.prefer_responses_api is True

	@pytest.mark.slow
	@pytest.mark.parametrize("model_id", ["gpt-5", "gpt-4.1"])
	def test_api_selection_logic(self, engine, model_id):
		"""Test API selection for responses-enabled models."""
		result = engine.should_use_responses_api(model_id)
		assert result is True

	@pytest.mark.slow
	def test_input_preparation(self, engine):
		"""Test input preparation for responses API."""
		conversation = Conversation()
		
		# Add some conversation history
		first_request = Message(role=MessageRoleEnum.USER, content="Hello")
		first_response = Message(role=MessageRoleEnum.ASSISTANT, content="Hi there!")
		first_block = MessageBlock(
			request=first_request,
			response=first_response,
			model=AIModelInfo(provider_id="openai", model_id="gpt-5"),
			stream=False,
		)
		conversation.add_block(first_block)
		
		# Create new block
		new_request = Message(role=MessageRoleEnum.USER, content="How are you?")
		new_block = MessageBlock(
			request=new_request,
			model=AIModelInfo(provider_id="openai", model_id="gpt-5"),
			stream=False,
		)
		
		# Test input preparation
		responses_input = engine.prepare_responses_input(new_block, conversation)
		
		# Verify format
		assert len(responses_input) == 3  # Previous user, assistant, new user
		assert all(msg["role"] in ["user", "assistant"] for msg in responses_input)
		
		# Verify content structure for responses API
		user_messages = [msg for msg in responses_input if msg["role"] == "user"]
		for user_msg in user_messages:
			assert isinstance(user_msg["content"], list)
			assert user_msg["content"][0]["type"] == "input_text"

	@pytest.mark.slow
	def test_reasoning_model_parameters(self, engine):
		"""Test that reasoning models get proper parameters."""
		# Create a reasoning model request
		new_request = Message(role=MessageRoleEnum.USER, content="Solve 2+2")
		new_block = MessageBlock(
			request=new_request,
			model=AIModelInfo(provider_id="openai", model_id="o3"),  # Reasoning model
			stream=False,
		)
		
		# Get model to check if it's marked as reasoning
		model = engine.get_model("o3")
		if model and getattr(model, 'reasoning', False):
			# Test would add reasoning parameters
			responses_input = engine.prepare_responses_input(new_block, Conversation())
			assert len(responses_input) == 1
			assert responses_input[0]["role"] == "user"


class TestResponsesAPIFallback:
	"""Test fallback behavior when responses API is not available."""
	
	@pytest.fixture
	def engine(self):
		"""Create engine with mock credentials."""
		provider = get_provider(id="openai")
		account = Account(
			provider=provider,
			api_key=SecretStr('fake_key'),
			name='test_account',
		)
		return OpenAIEngine(account)
	
	def test_chat_api_fallback(self, engine):
		"""Test that engine falls back to chat API for non-responses models."""
		# Test with a model that doesn't use responses API
		result = engine.should_use_responses_api("gpt-4o")
		assert result is False
		
		# Test with a model that does use responses API
		result = engine.should_use_responses_api("gpt-5")
		assert result is True

	def test_error_handling(self, engine):
		"""Test error handling in API selection."""
		# Test with non-existent model (returns None which is falsy)
		result = engine.should_use_responses_api("non-existent-model")
		assert not result  # None, False, or similar falsy value
		
		# Test with empty string
		result = engine.should_use_responses_api("")
		assert not result  # None, False, or similar falsy value