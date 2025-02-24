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


def test_add_message_to_conversation():
	"""Test adding a message to a conversation."""
	conv = Conversation()
	model = AIModelInfo(provider_id="anthropic", model_id="test")
	req_msg = Message(role=MessageRoleEnum.USER, content="Hello")
	msg_block = MessageBlock(request=req_msg, model=model)
	conv.add_block(msg_block)
	assert len(conv.messages) == 1
	assert conv.messages[0].request.content == "Hello"


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
