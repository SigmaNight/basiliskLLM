"""Unit tests for the Conversation module for the basiliskLLM application."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from basilisk.consts import BSKC_VERSION
from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.conversation.conversation_model import ResponseTiming, TokenUsage
from basilisk.provider_ai_model import AIModelInfo


class TestAIModelAndMessages:
	"""Tests for AI model and message validation."""

	def test_invalid_ai_model(self):
		"""Test invalid AI model."""
		with pytest.raises(ValidationError):
			AIModelInfo(
				provider_id="invalid_provider", model_id="invalid_model"
			)

	def test_invalid_msg_role(self):
		"""Test invalid message role."""
		with pytest.raises(ValidationError):
			Message(role="invalid_role", content="test")

	def test_create_message_block(self, ai_model, user_message):
		"""Test creating a message block."""
		block = MessageBlock(request=user_message, model=ai_model)
		assert block.request.content == "Test message"
		assert block.request.role == MessageRoleEnum.USER
		assert block.response is None
		assert block.model.provider_id == "openai"
		assert block.model.model_id == "test_model"

	def test_create_message_block_with_response(
		self, message_block_with_response
	):
		"""Test creating a message block with a response."""
		block = message_block_with_response
		assert block.request.content == "Test message"
		assert block.response.content == "Test response"
		assert block.model.provider_id == "openai"
		assert block.model.model_id == "test_model"
		assert block.request.role == MessageRoleEnum.USER
		assert block.response.role == MessageRoleEnum.ASSISTANT

	def test_message_block_reasoning_fields(self, ai_model, user_message):
		"""Test MessageBlock with reasoning mode fields."""
		block = MessageBlock(
			request=user_message,
			model=ai_model,
			reasoning_mode=True,
			reasoning_budget_tokens=16000,
			reasoning_effort="medium",
			reasoning_adaptive=False,
			web_search_mode=True,
		)
		assert block.reasoning_mode is True
		assert block.reasoning_budget_tokens == 16000
		assert block.reasoning_effort == "medium"
		assert block.reasoning_adaptive is False
		assert block.web_search_mode is True


class TestMessageBlockValidation:
	"""Tests for message block validation."""

	def test_invalid_request_role(self, ai_model, assistant_message):
		"""Test invalid request role."""
		with pytest.raises(ValidationError):
			MessageBlock(request=assistant_message, model=ai_model)

	def test_invalid_response_role(self, ai_model, user_message):
		"""Test invalid response role."""
		with pytest.raises(ValidationError):
			# Using user message as response (invalid)
			MessageBlock(
				request=user_message, response=user_message, model=ai_model
			)

	def test_message_block_no_request(self, ai_model, assistant_message):
		"""Test message block with no request."""
		with pytest.raises(ValidationError):
			MessageBlock(response=assistant_message, model=ai_model)

	def test_message_block_no_attachments_in_response(
		self, ai_model, attachment
	):
		"""Test message block with no attachments in response."""
		req_msg = Message(role=MessageRoleEnum.USER, content="test")
		res_msg = Message(
			role=MessageRoleEnum.ASSISTANT,
			content="test",
			attachments=[attachment],
		)

		with pytest.raises(ValidationError):
			MessageBlock(request=req_msg, response=res_msg, model=ai_model)


class TestConversationBasics:
	"""Tests for basic conversation functionality."""

	def test_create_empty_conversation(self, empty_conversation):
		"""Test creating an empty conversation."""
		assert empty_conversation.messages == []
		assert empty_conversation.systems == {}
		assert empty_conversation.title is None
		assert empty_conversation.version == BSKC_VERSION

	def test_invalid_min_conversation_version(self, empty_conversation):
		"""Test invalid minimum conversation version."""
		empty_conversation.version = -1
		json = empty_conversation.model_dump_json()
		with pytest.raises(ValidationError):
			Conversation.model_validate_json(json)

	def test_invalid_max_conversation_version(self, empty_conversation):
		"""Test invalid maximum conversation version."""
		empty_conversation.version = BSKC_VERSION + 1
		json = empty_conversation.model_dump_json()
		with pytest.raises(ValidationError):
			Conversation.model_validate_json(json)

	def test_add_block_without_system(self, empty_conversation, message_block):
		"""Test adding a message block to a conversation without a system message."""
		empty_conversation.add_block(message_block)

		assert len(empty_conversation.messages) == 1
		assert empty_conversation.messages[0] == message_block
		assert empty_conversation.messages[0].system_index is None
		assert len(empty_conversation.systems) == 0

	def test_add_block_with_system(
		self, empty_conversation, message_block, system_message
	):
		"""Test adding a message block to a conversation with a system message."""
		empty_conversation.add_block(message_block, system_message)

		assert len(empty_conversation.messages) == 1
		assert empty_conversation.messages[0] == message_block
		assert empty_conversation.messages[0].system_index == 0
		assert len(empty_conversation.systems) == 1
		assert system_message in empty_conversation.systems


class TestConversationWithMultipleBlocks:
	"""Tests for conversations with multiple message blocks."""

	@pytest.fixture
	def make_user_block(self, ai_model):
		"""Factory for creating user message blocks with given content."""

		def _make(content):
			return MessageBlock(
				request=Message(role=MessageRoleEnum.USER, content=content),
				model=ai_model,
			)

		return _make

	@pytest.fixture
	def make_system(self):
		"""Factory for creating system messages with given content."""

		def _make(content):
			return SystemMessage(role=MessageRoleEnum.SYSTEM, content=content)

		return _make

	def test_add_block_with_duplicate_system(
		self, empty_conversation, make_user_block, system_message
	):
		"""Test adding blocks with duplicate system messages."""
		first_block = make_user_block("First message")
		second_block = make_user_block("Second message")
		empty_conversation.add_block(first_block, system_message)
		empty_conversation.add_block(second_block, system_message)

		assert len(empty_conversation.messages) == 2
		assert empty_conversation.messages[0].system_index == 0
		assert empty_conversation.messages[1].system_index == 0
		assert (
			len(empty_conversation.systems) == 1
		)  # Only one unique system message

	def test_add_block_with_multiple_systems(
		self, empty_conversation, make_user_block, make_system
	):
		"""Test adding blocks with multiple different system messages."""
		first_block = make_user_block("First message")
		second_block = make_user_block("Second message")
		first_system = make_system("First system instructions")
		second_system = make_system("Second system instructions")
		empty_conversation.add_block(first_block, first_system)
		empty_conversation.add_block(second_block, second_system)

		assert len(empty_conversation.messages) == 2
		assert empty_conversation.messages[0].system_index == 0
		assert empty_conversation.messages[1].system_index == 1
		assert len(empty_conversation.systems) == 2
		assert first_system in empty_conversation.systems
		assert second_system in empty_conversation.systems

	def test_remove_block_without_system(
		self, empty_conversation, message_block
	):
		"""Test removing a message block without a system message."""
		empty_conversation.add_block(message_block)
		assert len(empty_conversation.messages) == 1

		empty_conversation.remove_block(message_block)
		assert len(empty_conversation.messages) == 0
		assert len(empty_conversation.systems) == 0

	def test_remove_block_with_system(
		self, empty_conversation, message_block, system_message
	):
		"""Test removing a message block with a system message."""
		empty_conversation.add_block(message_block, system_message)

		assert len(empty_conversation.messages) == 1
		assert empty_conversation.messages[0].system_index == 0
		assert empty_conversation.messages[0] == message_block
		assert system_message in empty_conversation.systems
		assert len(empty_conversation.systems) == 1

		empty_conversation.remove_block(message_block)
		assert len(empty_conversation.messages) == 0
		assert len(empty_conversation.systems) == 0

	def test_remove_block_with_shared_system(
		self, empty_conversation, make_user_block, system_message
	):
		"""Test removing a block that shares a system message with another block."""
		first_block = make_user_block("First message")
		second_block = make_user_block("Second message")
		empty_conversation.add_block(first_block, system_message)
		empty_conversation.add_block(second_block, system_message)

		assert len(empty_conversation.messages) == 2
		assert empty_conversation.messages[0].system_index == 0
		assert empty_conversation.messages[1].system_index == 0
		assert len(empty_conversation.systems) == 1

		empty_conversation.remove_block(first_block)
		assert len(empty_conversation.messages) == 1
		assert (
			empty_conversation.messages[0].system_index == 0
		)  # Index unchanged
		assert empty_conversation.messages[0] == second_block
		assert (
			len(empty_conversation.systems) == 1
		)  # System still used by remaining block

	def test_remove_block_with_multiple_systems(
		self, empty_conversation, make_user_block, make_system
	):
		"""Test removing blocks with multiple system messages."""
		first_block = make_user_block("First message")
		second_block = make_user_block("Second message")
		third_block = make_user_block("Third message")
		first_system = make_system("First system instructions")
		second_system = make_system("Second system instructions")
		empty_conversation.add_block(first_block, first_system)
		empty_conversation.add_block(second_block, second_system)
		empty_conversation.add_block(
			third_block, first_system
		)  # Reusing first system

		assert len(empty_conversation.messages) == 3
		assert empty_conversation.messages[0].system_index == 0
		assert empty_conversation.messages[1].system_index == 1
		assert empty_conversation.messages[2].system_index == 0
		assert len(empty_conversation.systems) == 2

		empty_conversation.remove_block(second_block)
		assert len(empty_conversation.messages) == 2
		assert empty_conversation.messages[0].system_index == 0
		assert empty_conversation.messages[1].system_index == 0
		assert len(empty_conversation.systems) == 1
		assert first_system in empty_conversation.systems
		assert second_system not in empty_conversation.systems

	def test_remove_block_with_index_adjustment(
		self, empty_conversation, make_user_block, make_system
	):
		"""Test system index adjustment when removing a system."""
		first_block = make_user_block("First message")
		second_block = make_user_block("Second message")
		third_block = make_user_block("Third message")
		first_system = make_system("First system instructions")
		second_system = make_system("Second system instructions")
		third_system = make_system("Third system instructions")
		empty_conversation.add_block(first_block, first_system)
		empty_conversation.add_block(second_block, second_system)
		empty_conversation.add_block(third_block, third_system)

		assert len(empty_conversation.messages) == 3
		assert empty_conversation.messages[0].system_index == 0
		assert empty_conversation.messages[1].system_index == 1
		assert empty_conversation.messages[2].system_index == 2
		assert len(empty_conversation.systems) == 3

		empty_conversation.remove_block(first_block)
		assert len(empty_conversation.messages) == 2
		assert empty_conversation.messages[0].system_index == 0  # Was 1, now 0
		assert empty_conversation.messages[1].system_index == 1  # Was 2, now 1
		assert len(empty_conversation.systems) == 2
		assert first_system not in empty_conversation.systems
		assert second_system in empty_conversation.systems
		assert third_system in empty_conversation.systems


class TestConversationProperties:
	"""Tests for Conversation computed properties (token usage, cost, models)."""

	def test_token_total_empty_conversation(self, empty_conversation):
		"""token_total is 0 when no blocks."""
		assert empty_conversation.token_total == 0

	def test_token_total_sums_block_usage(self, ai_model):
		"""token_total sums effective_total across blocks with usage."""
		conv = Conversation()
		for inp, out in [(100, 50), (200, 80)]:
			req = Message(role=MessageRoleEnum.USER, content="q")
			resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
			block = MessageBlock(
				request=req,
				response=resp,
				model=ai_model,
				usage=TokenUsage(input_tokens=inp, output_tokens=out),
			)
			conv.add_block(block)
		assert conv.token_total == 100 + 50 + 200 + 80

	def test_input_output_tokens_total(self, ai_model):
		"""input_tokens_total and output_tokens_total aggregate correctly."""
		conv = Conversation()
		req = Message(role=MessageRoleEnum.USER, content="q")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
		block = MessageBlock(
			request=req,
			response=resp,
			model=ai_model,
			usage=TokenUsage(input_tokens=100, output_tokens=50),
		)
		conv.add_block(block)
		assert conv.input_tokens_total == 100
		assert conv.output_tokens_total == 50

	def test_reasoning_cached_audio_totals(self, ai_model):
		"""reasoning_tokens_total, cached_input_tokens_total, audio_tokens_total."""
		conv = Conversation()
		req = Message(role=MessageRoleEnum.USER, content="q")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
		block = MessageBlock(
			request=req,
			response=resp,
			model=ai_model,
			usage=TokenUsage(
				input_tokens=100,
				output_tokens=50,
				reasoning_tokens=20,
				cached_input_tokens=30,
				audio_tokens=5,
			),
		)
		conv.add_block(block)
		assert conv.reasoning_tokens_total == 20
		assert conv.cached_input_tokens_total == 30
		assert conv.audio_tokens_total == 5

	def test_cost_total_from_block_cost(self, ai_model):
		"""cost_total sums block.cost when set."""
		conv = Conversation()
		for cost in [0.01, 0.02]:
			req = Message(role=MessageRoleEnum.USER, content="q")
			resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
			block = MessageBlock(
				request=req, response=resp, model=ai_model, cost=cost
			)
			conv.add_block(block)
		assert conv.cost_total == 0.03

	def test_cost_total_from_usage_cost(self, ai_model):
		"""cost_total uses usage.cost when block.cost not set."""
		conv = Conversation()
		req = Message(role=MessageRoleEnum.USER, content="q")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
		block = MessageBlock(
			request=req,
			response=resp,
			model=ai_model,
			usage=TokenUsage(input_tokens=10, output_tokens=5, cost=0.001),
		)
		conv.add_block(block)
		assert conv.cost_total == 0.001

	def test_cost_total_none_when_no_costs(self, ai_model):
		"""cost_total is None when no blocks have cost."""
		conv = Conversation()
		req = Message(role=MessageRoleEnum.USER, content="q")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
		block = MessageBlock(request=req, response=resp, model=ai_model)
		conv.add_block(block)
		assert conv.cost_total is None

	def test_models_used_unique_ordered(self, ai_model):
		"""models_used returns unique model ids in order of first use."""
		other_model = AIModelInfo(provider_id="anthropic", model_id="claude-3")
		conv = Conversation()
		for model in [ai_model, other_model, ai_model]:
			req = Message(role=MessageRoleEnum.USER, content="q")
			resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
			block = MessageBlock(request=req, response=resp, model=model)
			conv.add_block(block)
		assert conv.models_used == ["openai/test_model", "anthropic/claude-3"]

	def test_block_count(self, empty_conversation, message_block):
		"""block_count equals len(messages)."""
		assert empty_conversation.block_count == 0
		empty_conversation.add_block(message_block)
		assert empty_conversation.block_count == 1

	def test_started_at_last_activity_at(self, ai_model):
		"""started_at and last_activity_at from block timestamps."""
		base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
		conv = Conversation()
		for i in range(2):
			req = Message(role=MessageRoleEnum.USER, content="q")
			resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
			block = MessageBlock(
				request=req,
				response=resp,
				model=ai_model,
				created_at=base.replace(hour=12 + i),
				updated_at=base.replace(hour=12 + i, minute=30),
			)
			conv.add_block(block)
		assert conv.started_at == base.replace(hour=12)
		assert conv.last_activity_at == base.replace(hour=13, minute=30)

	def test_total_duration_seconds(self, ai_model):
		"""total_duration_seconds from first start to last finish."""
		base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
		conv = Conversation()
		req = Message(role=MessageRoleEnum.USER, content="q")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
		block = MessageBlock(
			request=req,
			response=resp,
			model=ai_model,
			timing=ResponseTiming(
				started_at=base, finished_at=base.replace(second=10)
			),
		)
		conv.add_block(block)
		assert conv.total_duration_seconds == 10.0

	def test_average_tokens_per_block(self, ai_model):
		"""average_tokens_per_block is token_total / block_count."""
		conv = Conversation()
		for _ in range(2):
			req = Message(role=MessageRoleEnum.USER, content="q")
			resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
			block = MessageBlock(
				request=req,
				response=resp,
				model=ai_model,
				usage=TokenUsage(input_tokens=100, output_tokens=50),
			)
			conv.add_block(block)
		assert conv.average_tokens_per_block == 150.0
