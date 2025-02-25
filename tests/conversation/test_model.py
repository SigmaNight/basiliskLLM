"""Unit tests for the Conversation module for the basiliskLLM application."""

import pytest
from pydantic import ValidationError
from upath import UPath

from basilisk.conversation import (
	AttachmentFile,
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.provider_ai_model import AIModelInfo


def test_invalid_ai_model():
	"""Test invalid AI model."""
	with pytest.raises(ValidationError) as exc_info:
		AIModelInfo(provider_id="invalid_provider", model_id="invalid_model")
		assert exc_info.group_contains(ValueError, "No provider found")


def test_invalid_msg_role():
	"""Test invalid message role."""
	with pytest.raises(ValidationError):
		Message(role="invalid_role", content="test")


def test_create_message_block():
	"""Test creating a message block."""
	model = AIModelInfo(provider_id="openai", model_id="test_model")
	msg = Message(role=MessageRoleEnum.USER, content="Test message")
	block = MessageBlock(request=msg, model=model)
	assert block.request.content == "Test message"
	assert block.request.role == MessageRoleEnum.USER
	assert block.response is None
	assert block.model.provider_id == "openai"
	assert block.model.model_id == "test_model"


def test_create_message_block_with_response():
	"""Test creating a message block with a response."""
	model = AIModelInfo(provider_id="openai", model_id="test_model")
	req_msg = Message(role=MessageRoleEnum.USER, content="Test request")
	res_msg = Message(role=MessageRoleEnum.ASSISTANT, content="Test response")
	block = MessageBlock(request=req_msg, response=res_msg, model=model)
	assert block.request.content == "Test request"
	assert block.response.content == "Test response"
	assert block.model.provider_id == "openai"
	assert block.model.model_id == "test_model"
	assert block.request.role == MessageRoleEnum.USER
	assert block.response.role == MessageRoleEnum.ASSISTANT


def test_invalid_request_role():
	"""Test invalid request role."""
	model = AIModelInfo(provider_id="openai", model_id="test_model")
	req_msg = Message(
		role=MessageRoleEnum.ASSISTANT, content="Test request"
	)  # Invalid role
	res_msg = Message(role=MessageRoleEnum.ASSISTANT, content="Test response")
	with pytest.raises(ValidationError) as exc_info:
		MessageBlock(request=req_msg, response=res_msg, model=model)
		assert exc_info.group_contains(
			ValueError, "Request message must be from the user."
		)


def test_invalid_response_role():
	"""Test invalid message block."""
	model = AIModelInfo(provider_id="openai", model_id="test_model")
	req_msg = Message(role=MessageRoleEnum.USER, content="Test request")
	res_msg = Message(
		role=MessageRoleEnum.USER, content="Test response"
	)  # Invalid role
	with pytest.raises(ValidationError) as exc_info:
		MessageBlock(request=req_msg, response=res_msg, model=model)
		assert exc_info.group_contains(
			ValueError, "Response message must be from the assistant."
		)


def test_message_block_no_request():
	"""Test message block with no request."""
	model = AIModelInfo(provider_id="openai", model_id="test")
	res_msg = Message(role=MessageRoleEnum.ASSISTANT, content="test")
	with pytest.raises(ValidationError):
		MessageBlock(response=res_msg, model=model)


def test_message_block_no_attachments_in_response(tmp_path: str):
	"""Test message block with no attachments in response."""
	test_file = UPath(tmp_path) / "test.txt"
	with test_file.open("w") as f:
		f.write("test")
	attachment = AttachmentFile(location=test_file)
	model = AIModelInfo(provider_id="openai", model_id="test")
	req_msg = Message(
		role=MessageRoleEnum.USER, content="test", attachments=None
	)
	res_msg = Message(
		role=MessageRoleEnum.ASSISTANT, content="test", attachments=[attachment]
	)
	with pytest.raises(ValidationError) as exc_info:
		MessageBlock(request=req_msg, response=res_msg, model=model)
		assert exc_info.group_contains(
			ValueError, "Response messages cannot have attachments."
		)


def test_create_empty_conversation():
	"""Test creating an empty conversation."""
	conv = Conversation()
	assert conv.messages == []
	assert conv.systems == {}
	assert conv.title is None


def test_add_block_without_system():
	"""Test adding a message block to a conversation without a system message."""
	conv = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")
	req_msg = Message(role=MessageRoleEnum.USER, content="Test message")
	block = MessageBlock(request=req_msg, model=model)

	# Add block to conversation without system message
	conv.add_block(block)

	# Verify block was added correctly
	assert len(conv.messages) == 1
	assert conv.messages[0] == block
	assert conv.messages[0].system_index is None
	assert len(conv.systems) == 0


def test_add_block_with_system():
	"""Test adding a message block to a conversation with a system message."""
	conv = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")
	req_msg = Message(role=MessageRoleEnum.USER, content="Test message")
	block = MessageBlock(request=req_msg, model=model)
	system_msg = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="System instructions"
	)

	# Add block to conversation with system message
	conv.add_block(block, system_msg)

	# Verify block and system message were added correctly
	assert len(conv.messages) == 1
	assert conv.messages[0] == block
	assert conv.messages[0].system_index == 0
	assert len(conv.systems) == 1
	assert system_msg in conv.systems


def test_add_block_with_duplicate_system():
	"""Test adding blocks with duplicate system messages."""
	conv = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")

	# Create two blocks and a system message
	req_msg1 = Message(role=MessageRoleEnum.USER, content="First message")
	block1 = MessageBlock(request=req_msg1, model=model)
	req_msg2 = Message(role=MessageRoleEnum.USER, content="Second message")
	block2 = MessageBlock(request=req_msg2, model=model)
	system_msg = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="System instructions"
	)

	# Add blocks with the same system message
	conv.add_block(block1, system_msg)
	conv.add_block(block2, system_msg)

	# Verify blocks were added with the same system index
	assert len(conv.messages) == 2
	assert conv.messages[0].system_index == 0
	assert conv.messages[1].system_index == 0
	assert len(conv.systems) == 1  # Only one unique system message


def test_add_block_with_multiple_systems():
	"""Test adding blocks with multiple different system messages."""
	conv = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")

	# Create blocks and system messages
	req_msg1 = Message(role=MessageRoleEnum.USER, content="First message")
	block1 = MessageBlock(request=req_msg1, model=model)
	req_msg2 = Message(role=MessageRoleEnum.USER, content="Second message")
	block2 = MessageBlock(request=req_msg2, model=model)

	system_msg1 = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="First system instructions"
	)
	system_msg2 = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="Second system instructions"
	)

	# Add blocks with different system messages
	conv.add_block(block1, system_msg1)
	conv.add_block(block2, system_msg2)

	# Verify blocks were added with different system indices
	assert len(conv.messages) == 2
	assert conv.messages[0].system_index == 0
	assert conv.messages[1].system_index == 1
	assert len(conv.systems) == 2
	assert system_msg1 in conv.systems
	assert system_msg2 in conv.systems


def test_remove_block_without_system():
	"""Test removing a message block without a system message."""
	conv = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")

	# Create and add block without system
	req_msg = Message(role=MessageRoleEnum.USER, content="Test message")
	block = MessageBlock(request=req_msg, model=model)
	conv.add_block(block)

	# Verify block was added
	assert len(conv.messages) == 1

	# Remove the block
	conv.remove_block(block)

	# Verify block was removed
	assert len(conv.messages) == 0
	assert len(conv.systems) == 0


def test_remove_block_with_system():
	"""Test removing a message block with a system message."""
	conv = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")

	# Create and add block with system
	req_msg = Message(role=MessageRoleEnum.USER, content="Test message")
	block = MessageBlock(request=req_msg, model=model)
	system_msg = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="System instructions"
	)
	conv.add_block(block, system_msg)

	# Verify block was added with system
	assert len(conv.messages) == 1
	assert conv.messages[0].system_index == 0
	assert conv.messages[0] == block
	assert system_msg in conv.systems
	assert len(conv.systems) == 1

	# Remove the block
	conv.remove_block(block)

	# Verify block and system were removed
	assert len(conv.messages) == 0
	assert len(conv.systems) == 0


def test_remove_block_with_shared_system():
	"""Test removing a block that shares a system message with another block."""
	conv = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")

	# Create two blocks
	req_msg1 = Message(role=MessageRoleEnum.USER, content="First message")
	block1 = MessageBlock(request=req_msg1, model=model)
	req_msg2 = Message(role=MessageRoleEnum.USER, content="Second message")
	block2 = MessageBlock(request=req_msg2, model=model)

	# Create one system message for both blocks
	system_msg = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="System instructions"
	)

	# Add blocks with the same system message
	conv.add_block(block1, system_msg)
	conv.add_block(block2, system_msg)

	# Verify two blocks with same system
	assert len(conv.messages) == 2
	assert conv.messages[0].system_index == 0
	assert conv.messages[1].system_index == 0
	assert len(conv.systems) == 1

	# Remove first block
	conv.remove_block(block1)

	# Verify one block remains with system intact
	assert len(conv.messages) == 1
	assert conv.messages[0].system_index == 0  # Index unchanged
	assert conv.messages[0] == block2
	assert len(conv.systems) == 1  # System still used by remaining block


def test_remove_block_with_multiple_systems():
	"""Test removing blocks with multiple system messages."""
	conv = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")

	# Create three blocks
	req_msg1 = Message(role=MessageRoleEnum.USER, content="First message")
	block1 = MessageBlock(request=req_msg1, model=model)
	req_msg2 = Message(role=MessageRoleEnum.USER, content="Second message")
	block2 = MessageBlock(request=req_msg2, model=model)
	req_msg3 = Message(role=MessageRoleEnum.USER, content="Third message")
	block3 = MessageBlock(request=req_msg3, model=model)

	# Create two system messages
	system_msg1 = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="First system instructions"
	)
	system_msg2 = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="Second system instructions"
	)

	# Add blocks with different system messages
	conv.add_block(block1, system_msg1)
	conv.add_block(block2, system_msg2)
	conv.add_block(block3, system_msg1)  # Reusing first system

	# Verify initial state
	assert len(conv.messages) == 3
	assert conv.messages[0].system_index == 0
	assert conv.messages[1].system_index == 1
	assert conv.messages[2].system_index == 0
	assert len(conv.systems) == 2

	# Remove the middle block (the one with system_msg2)
	conv.remove_block(block2)

	# Verify middle block removed and its system message too
	assert len(conv.messages) == 2
	assert conv.messages[0].system_index == 0
	assert conv.messages[1].system_index == 0
	assert len(conv.systems) == 1
	assert system_msg1 in conv.systems
	assert system_msg2 not in conv.systems


def test_remove_block_with_index_adjustment():
	"""Test system index adjustment when removing a system."""
	conv = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")

	# Create three blocks
	req_msg1 = Message(role=MessageRoleEnum.USER, content="First message")
	block1 = MessageBlock(request=req_msg1, model=model)
	req_msg2 = Message(role=MessageRoleEnum.USER, content="Second message")
	block2 = MessageBlock(request=req_msg2, model=model)
	req_msg3 = Message(role=MessageRoleEnum.USER, content="Third message")
	block3 = MessageBlock(request=req_msg3, model=model)

	# Create three system messages
	system_msg1 = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="First system instructions"
	)
	system_msg2 = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="Second system instructions"
	)
	system_msg3 = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="Third system instructions"
	)

	# Add blocks with different system messages
	conv.add_block(block1, system_msg1)
	conv.add_block(block2, system_msg2)
	conv.add_block(block3, system_msg3)

	# Verify initial state
	assert len(conv.messages) == 3
	assert conv.messages[0].system_index == 0
	assert conv.messages[1].system_index == 1
	assert conv.messages[2].system_index == 2
	assert len(conv.systems) == 3

	# Remove the first block (with system_msg1)
	conv.remove_block(block1)

	# Verify system indices were adjusted
	assert len(conv.messages) == 2
	assert conv.messages[0].system_index == 0  # Was 1, now 0
	assert conv.messages[1].system_index == 1  # Was 2, now 1
	assert len(conv.systems) == 2
	assert system_msg1 not in conv.systems
	assert system_msg2 in conv.systems
	assert system_msg3 in conv.systems
