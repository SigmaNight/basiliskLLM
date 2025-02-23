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
	assert conv.system is None
	assert conv.title is None


def test_add_message_to_conversation():
	conv = Conversation()
	model = AIModelInfo(provider_id="anthropic", model_id="test")
	req_msg = Message(role=MessageRoleEnum.USER, content="Hello")
	msg_block = MessageBlock(request=req_msg, model=model)
	conv.messages.append(msg_block)
	assert len(conv.messages) == 1
	assert conv.messages[0].request.content == "Hello"
