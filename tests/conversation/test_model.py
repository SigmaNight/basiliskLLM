"""Unit tests for the Conversation module for the basiliskLLM application."""

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
from basilisk.provider_ai_model import AIModelInfo


class TestAIModelAndMessages:
	"""Tests for AI model and message validation."""

	def test_invalid_ai_model(self):
		"""Test invalid AI model."""
		with pytest.raises(ValidationError) as exc_info:
			AIModelInfo(
				provider_id="invalid_provider", model_id="invalid_model"
			)
			assert exc_info.group_contains(ValueError, "No provider found")

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


class TestMessageBlockValidation:
	"""Tests for message block validation."""

	def test_invalid_request_role(self, ai_model, assistant_message):
		"""Test invalid request role."""
		with pytest.raises(ValidationError) as exc_info:
			MessageBlock(request=assistant_message, model=ai_model)
			assert exc_info.group_contains(
				ValueError, "Request message must be from the user."
			)

	def test_invalid_response_role(self, ai_model, user_message):
		"""Test invalid response role."""
		with pytest.raises(ValidationError) as exc_info:
			# Using user message as response (invalid)
			MessageBlock(
				request=user_message, response=user_message, model=ai_model
			)
			assert exc_info.group_contains(
				ValueError, "Response message must be from the assistant."
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

		with pytest.raises(ValidationError) as exc_info:
			MessageBlock(request=req_msg, response=res_msg, model=ai_model)
			assert exc_info.group_contains(
				ValueError, "Response messages cannot have attachments."
			)


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
	def first_block(self, ai_model):
		"""Return a first message block."""
		req_msg = Message(role=MessageRoleEnum.USER, content="First message")
		return MessageBlock(request=req_msg, model=ai_model)

	@pytest.fixture
	def second_block(self, ai_model):
		"""Return a second message block."""
		req_msg = Message(role=MessageRoleEnum.USER, content="Second message")
		return MessageBlock(request=req_msg, model=ai_model)

	@pytest.fixture
	def third_block(self, ai_model):
		"""Return a third message block."""
		req_msg = Message(role=MessageRoleEnum.USER, content="Third message")
		return MessageBlock(request=req_msg, model=ai_model)

	@pytest.fixture
	def first_system(self):
		"""Return a first system message."""
		return SystemMessage(
			role=MessageRoleEnum.SYSTEM, content="First system instructions"
		)

	@pytest.fixture
	def second_system(self):
		"""Return a second system message."""
		return SystemMessage(
			role=MessageRoleEnum.SYSTEM, content="Second system instructions"
		)

	@pytest.fixture
	def third_system(self):
		"""Return a third system message."""
		return SystemMessage(
			role=MessageRoleEnum.SYSTEM, content="Third system instructions"
		)

	def test_add_block_with_duplicate_system(
		self, empty_conversation, first_block, second_block, system_message
	):
		"""Test adding blocks with duplicate system messages."""
		empty_conversation.add_block(first_block, system_message)
		empty_conversation.add_block(second_block, system_message)

		assert len(empty_conversation.messages) == 2
		assert empty_conversation.messages[0].system_index == 0
		assert empty_conversation.messages[1].system_index == 0
		assert (
			len(empty_conversation.systems) == 1
		)  # Only one unique system message

	def test_add_block_with_multiple_systems(
		self,
		empty_conversation,
		first_block,
		second_block,
		first_system,
		second_system,
	):
		"""Test adding blocks with multiple different system messages."""
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
		self, empty_conversation, first_block, second_block, system_message
	):
		"""Test removing a block that shares a system message with another block."""
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
		self,
		empty_conversation,
		first_block,
		second_block,
		third_block,
		first_system,
		second_system,
	):
		"""Test removing blocks with multiple system messages."""
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
		self,
		empty_conversation,
		first_block,
		second_block,
		third_block,
		first_system,
		second_system,
		third_system,
	):
		"""Test system index adjustment when removing a system."""
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
