#!/usr/bin/env python3
"""Integration tests for OpenAI Responses API with comprehensive mocking.

This module tests the integration logic of the OpenAI Responses API implementation
using mocks to avoid real API calls. It provides comprehensive coverage of all
code paths, error scenarios, and edge cases.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

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


class TestResponsesAPIIntegration:
	"""Comprehensive integration tests using mocks."""
	
	@pytest.fixture
	def engine(self):
		"""Create engine with mock credentials."""
		provider = get_provider(id="openai")
		account = Account(
			provider=provider,
			api_key=SecretStr('test_key'),
			name='test_account',
		)
		return OpenAIEngine(account)
	
	@pytest.fixture
	def conversation_with_history(self):
		"""Create conversation with existing message history."""
		conversation = Conversation()
		
		# Add a completed exchange
		first_request = Message(
			role=MessageRoleEnum.USER, content="What is 2 + 2?"
		)
		first_response = Message(
			role=MessageRoleEnum.ASSISTANT, content="2 + 2 equals 4."
		)
		first_block = MessageBlock(
			request=first_request,
			response=first_response,
			model=AIModelInfo(provider_id="openai", model_id="gpt-4o"),
			stream=False,
		)
		conversation.add_block(first_block)
		
		return conversation
	
	def test_responses_api_input_preparation(self, engine, conversation_with_history):
		"""Test input preparation for responses API with conversation history."""
		new_request = Message(
			role=MessageRoleEnum.USER, content="What about 3 + 3?"
		)
		new_block = MessageBlock(
			request=new_request,
			model=AIModelInfo(provider_id="openai", model_id="gpt-5"),
			stream=False,
			max_tokens=100,
		)
		
		# Test input preparation
		responses_input = engine.prepare_responses_input(
			new_block, conversation_with_history
		)
		
		# Verify structure
		assert len(responses_input) == 3
		assert responses_input[0]["role"] == "user"
		assert responses_input[1]["role"] == "assistant"
		assert responses_input[2]["role"] == "user"
		
		# Verify content format for responses API
		user_content = responses_input[2]["content"]
		assert isinstance(user_content, list)
		assert user_content[0]["type"] == "input_text"
		assert user_content[0]["text"] == "What about 3 + 3?"

	@pytest.mark.parametrize("model_id,expected_api", [
		("gpt-5", True),
		("gpt-5-mini", True),
		("gpt-4.1", True),
		("gpt-4o", False),
		("gpt-4o-mini", False),
	])
	def test_api_selection_logic(self, engine, model_id, expected_api):
		"""Test API selection for different models."""
		result = engine.should_use_responses_api(model_id)
		assert result == expected_api

	def test_responses_api_completion_flow(self, engine, conversation_with_history):
		"""Test complete responses API flow with mocking."""
		new_request = Message(
			role=MessageRoleEnum.USER, content="What about 3 + 3?"
		)
		new_block = MessageBlock(
			request=new_request,
			model=AIModelInfo(provider_id="openai", model_id="gpt-5"),
			stream=False,
			max_tokens=100,
		)
		
		# Mock responses API response
		mock_response = Mock()
		mock_response.output_text = "3 + 3 equals 6."
		
		with patch.object(engine, 'client') as mock_client:
			# Set up responses API mock
			mock_client.responses = Mock()
			mock_client.responses.create.return_value = mock_response
			
			# Test completion
			result = engine.completion(new_block, conversation_with_history, None)
			
			# Verify responses API was called
			mock_client.responses.create.assert_called_once()
			call_args = mock_client.responses.create.call_args
			
			# Verify call parameters
			assert call_args[1]["model"] == "gpt-5"
			assert not call_args[1]["stream"]
			assert call_args[1]["max_output_tokens"] == 100
			assert len(call_args[1]["input"]) == 3
			
			# Test response processing
			assert result == mock_response
			result_block = engine.completion_response_without_stream(
				mock_response, new_block
			)
			
			assert result_block.response is not None
			assert result_block.response.content == "3 + 3 equals 6."
			assert result_block.response.role == MessageRoleEnum.ASSISTANT

	def test_chat_api_fallback_flow(self, engine, conversation_with_history):
		"""Test fallback to chat API for non-responses models."""
		new_request = Message(
			role=MessageRoleEnum.USER, content="What about 3 + 3?"
		)
		chat_block = MessageBlock(
			request=new_request,
			model=AIModelInfo(provider_id="openai", model_id="gpt-4o"),
			stream=False,
		)
		
		# Mock chat API response - ensure it doesn't have output_text
		mock_chat_response = Mock()
		# Remove output_text attribute to ensure it's detected as chat API response
		if hasattr(mock_chat_response, 'output_text'):
			delattr(mock_chat_response, 'output_text')
		mock_chat_response.choices = [Mock()]
		mock_chat_response.choices[0].message = Mock()
		mock_chat_response.choices[0].message.content = "Chat API response"
		
		with patch.object(engine, 'client') as mock_client:
			mock_client.chat.completions.create.return_value = mock_chat_response
			
			result = engine.completion(chat_block, conversation_with_history, None)
			
			# Verify chat API was called
			mock_client.chat.completions.create.assert_called_once()
			
			# Test response processing
			assert result == mock_chat_response
			result_block = engine.completion_response_without_stream(
				mock_chat_response, chat_block
			)
			
			assert result_block.response.content == "Chat API response"

	@pytest.mark.parametrize("chunk_type,chunk_data,expected", [
		("response.output_text.delta", {"delta": "Hello"}, ["Hello"]),
		("response.output_item.added", {"item": {"content": [{"type": "output_text", "text": "World"}]}}, ["World"]),
		("response.completed", {"response": {"output_text": "Complete"}}, ["Complete"]),
	])
	def test_streaming_event_handling(self, engine, chunk_type, chunk_data, expected):
		"""Test different streaming event types."""
		# Create mock chunk
		mock_chunk = Mock()
		mock_chunk.type = chunk_type
		
		# Set up chunk data based on type
		if chunk_type == "response.output_text.delta":
			mock_chunk.delta = chunk_data["delta"]
		elif chunk_type == "response.output_item.added":
			mock_chunk.item = Mock()
			mock_chunk.item.content = [Mock()]
			mock_chunk.item.content[0].type = "output_text"
			mock_chunk.item.content[0].text = chunk_data["item"]["content"][0]["text"]
		elif chunk_type == "response.completed":
			mock_chunk.response = Mock()
			mock_chunk.response.output_text = chunk_data["response"]["output_text"]
		
		# Test streaming
		stream_content = list(
			engine.completion_response_with_stream([mock_chunk])
		)
		
		assert stream_content == expected

	def test_chat_api_streaming(self, engine):
		"""Test chat API streaming compatibility."""
		# Create mock chat chunk
		mock_chat_chunk = Mock()
		# Chat chunks don't have 'type' attribute
		if hasattr(mock_chat_chunk, 'type'):
			delattr(mock_chat_chunk, 'type')
		mock_chat_chunk.choices = [Mock()]
		mock_chat_chunk.choices[0].delta = Mock()
		mock_chat_chunk.choices[0].delta.content = 'Chat streaming content'
		
		stream_content = list(
			engine.completion_response_with_stream([mock_chat_chunk])
		)
		
		assert stream_content == ['Chat streaming content']

	def test_error_handling_responses_api_unavailable(self, engine):
		"""Test fallback when responses API is not available."""
		new_block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Test"),
			model=AIModelInfo(provider_id="openai", model_id="gpt-5"),
			stream=False,
		)
		
		with patch.object(engine, 'client') as mock_client:
			# Remove responses attribute to simulate unavailable API
			if hasattr(mock_client, 'responses'):
				delattr(mock_client, 'responses')
			
			# Mock chat API as fallback
			mock_chat_response = Mock()
			if hasattr(mock_chat_response, 'output_text'):
				delattr(mock_chat_response, 'output_text')
			mock_chat_response.choices = [Mock()]
			mock_chat_response.choices[0].message = Mock()
			mock_chat_response.choices[0].message.content = "Fallback response"
			mock_client.chat.completions.create.return_value = mock_chat_response
			
			# Should fallback to chat API
			result = engine.completion(new_block, Conversation(), None)
			
			# Verify fallback occurred
			mock_client.chat.completions.create.assert_called_once()
			assert result == mock_chat_response

	def test_error_handling_responses_api_exception(self, engine):
		"""Test fallback when responses API raises an exception."""
		new_block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Test"),
			model=AIModelInfo(provider_id="openai", model_id="gpt-5"),
			stream=False,
		)
		
		with patch.object(engine, 'client') as mock_client:
			# Set up responses API to raise exception
			mock_client.responses = Mock()
			mock_client.responses.create.side_effect = Exception("API Error")
			
			# Mock chat API as fallback
			mock_chat_response = Mock()
			if hasattr(mock_chat_response, 'output_text'):
				delattr(mock_chat_response, 'output_text')
			mock_chat_response.choices = [Mock()]
			mock_chat_response.choices[0].message = Mock()
			mock_chat_response.choices[0].message.content = "Fallback response"
			mock_client.chat.completions.create.return_value = mock_chat_response
			
			# Should fallback to chat API
			result = engine.completion(new_block, Conversation(), None)
			
			# Verify both APIs were called
			mock_client.responses.create.assert_called_once()
			mock_client.chat.completions.create.assert_called_once()
			assert result == mock_chat_response

	def test_reasoning_model_parameters(self, engine):
		"""Test reasoning parameters are added for reasoning models."""
		# Create a reasoning model block
		new_block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Test reasoning"),
			model=AIModelInfo(provider_id="openai", model_id="gpt-5"),  # Assume reasoning
			stream=False,
		)
		
		# Mock a reasoning model
		with patch.object(engine, 'get_model') as mock_get_model:
			mock_model = Mock()
			mock_model.reasoning = True
			mock_get_model.return_value = mock_model
			
			with patch.object(engine, 'client') as mock_client:
				mock_client.responses = Mock()
				mock_response = Mock()
				mock_response.output_text = "Reasoning response"
				mock_client.responses.create.return_value = mock_response
				
				# Test completion
				engine.completion(new_block, Conversation(), None)
				
				# Verify reasoning parameter was added
				call_args = mock_client.responses.create.call_args
				assert "reasoning" in call_args[1]
				assert call_args[1]["reasoning"] == {"effort": "medium"}

	def test_response_extraction_edge_cases(self, engine):
		"""Test edge cases in response content extraction."""
		new_block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Test"),
			model=AIModelInfo(provider_id="openai", model_id="gpt-5"),
			stream=False,
		)
		
		# Test empty output_text
		mock_response = Mock()
		mock_response.output_text = ""
		mock_response.output = [Mock()]
		mock_response.output[0].type = "message"
		mock_response.output[0].content = [Mock()]
		mock_response.output[0].content[0].type = "output_text"
		mock_response.output[0].content[0].text = "Extracted from output items"
		
		result_block = engine.completion_response_without_stream(
			mock_response, new_block
		)
		
		assert result_block.response.content == "Extracted from output items"
		
		# Test completely empty response
		empty_response = Mock()
		empty_response.output_text = ""
		empty_response.output = []
		
		result_block = engine.completion_response_without_stream(
			empty_response, new_block
		)
		
		assert result_block.response.content == ""