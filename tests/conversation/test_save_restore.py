"""Unit tests for saving and restoring conversations."""

import json
import os
import zipfile

import pytest
from PIL import Image
from upath import UPath

from basilisk.conversation import (
	AttachmentFile,
	Conversation,
	ImageFile,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.provider_ai_model import AIModelInfo


def test_save_empty_conversation(tmp_path: str):
	"""Test saving an empty conversation."""
	temp_path = f"{tmp_path}{os.sep}test_conversation.bskc"
	conversation = Conversation()
	conversation.save(temp_path)
	assert os.path.exists(temp_path)
	assert zipfile.is_zipfile(temp_path)
	with zipfile.ZipFile(temp_path, "r") as zip_file:
		assert "conversation.json" in zip_file.namelist()
		with zip_file.open("conversation.json") as json_file:
			data = json.load(json_file)
			assert data == {"messages": [], "systems": [], "title": None}


def test_restore_empty_conversation(tmp_path: str):
	"""Test restoring an empty conversation."""
	temp_path = f"{tmp_path}{os.sep}test_conversation.bskc"
	with zipfile.ZipFile(temp_path, "w") as zip_file:
		with zip_file.open("conversation.json", "w") as json_file:
			conv = {"messages": [], "systems": [], "title": None}
			conv = json.dumps(conv).encode("utf-8")
			json_file.write(conv)
	base_storage_path = UPath("memory://test_restore")
	restored_conversation = Conversation.open(temp_path, base_storage_path)

	assert isinstance(restored_conversation, Conversation)
	assert len(restored_conversation.messages) == 0
	assert len(restored_conversation.systems) == 0
	assert restored_conversation.title is None


def test_save_restore_conversation_with_messages(tmp_path: str):
	"""Test saving and restoring a conversation with messages."""
	conversation = Conversation()
	conversation.title = "Test Conversation"

	model = AIModelInfo(provider_id="openai", model_id="test_model")

	request1 = Message(role=MessageRoleEnum.USER, content="Test message 1")
	response1 = Message(
		role=MessageRoleEnum.ASSISTANT, content="Test response 1"
	)
	block1 = MessageBlock(request=request1, response=response1, model=model)

	request2 = Message(role=MessageRoleEnum.USER, content="Test message 2")
	block2 = MessageBlock(request=request2, model=model)

	conversation.add_block(block1)
	conversation.add_block(block2)

	temp_path = f"{tmp_path}{os.sep}test_conversation.bskc"
	conversation.save(temp_path)

	storage_path = UPath("memory://test_restore")

	restored_conversation = Conversation.open(temp_path, storage_path)

	assert isinstance(restored_conversation, Conversation)
	assert restored_conversation.title == "Test Conversation"
	assert len(restored_conversation.messages) == 2
	assert restored_conversation.messages[0].request.content == "Test message 1"
	assert (
		restored_conversation.messages[0].response.content == "Test response 1"
	)
	assert restored_conversation.messages[0].model.provider_id == "openai"
	assert restored_conversation.messages[0].model.model_id == "test_model"

	assert restored_conversation.messages[1].request.content == "Test message 2"
	assert restored_conversation.messages[1].response is None
	assert restored_conversation.messages[1].model.provider_id == "openai"


def test_save_restore_conversation_with_system_messages(tmp_path: str):
	"""Test saving and restoring a conversation with system messages."""
	conversation = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")

	system1 = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="System instructions 1"
	)

	system2 = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="System instructions 2"
	)

	request1 = Message(role=MessageRoleEnum.USER, content="Test message 1")
	block1 = MessageBlock(request=request1, model=model)

	request2 = Message(role=MessageRoleEnum.USER, content="Test message 2")
	block2 = MessageBlock(request=request2, model=model)

	conversation.add_block(block1, system1)
	conversation.add_block(block2, system2)

	temp_path = f"{tmp_path}{os.sep}test_conversation.bskc"

	conversation.save(temp_path)
	storage_path = UPath("memory://test_system_restore")
	restored_conversation = Conversation.open(temp_path, storage_path)
	assert isinstance(restored_conversation, Conversation)
	assert len(restored_conversation.systems) == 2
	assert restored_conversation.systems[0].content == "System instructions 1"
	assert restored_conversation.systems[1].content == "System instructions 2"
	assert restored_conversation.messages[0].system_index == 0
	assert restored_conversation.messages[1].system_index == 1


def test_save_restore_conversation_with_shared_system_message(tmp_path: str):
	"""Test saving and restoring a conversation with shared system messages."""
	conversation = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")
	system = SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="Shared system instructions"
	)
	request1 = Message(role=MessageRoleEnum.USER, content="Test message 1")
	block1 = MessageBlock(request=request1, model=model)

	request2 = Message(role=MessageRoleEnum.USER, content="Test message 2")
	block2 = MessageBlock(request=request2, model=model)

	conversation.add_block(block1, system)
	conversation.add_block(block2, system)

	temp_path = f"{tmp_path}{os.sep}test_conversation.bskc"
	conversation.save(temp_path)

	storage_path = UPath("memory://test_shared_system_restore")
	restored_conversation = Conversation.open(temp_path, storage_path)

	assert isinstance(restored_conversation, Conversation)
	assert len(restored_conversation.systems) == 1
	assert (
		restored_conversation.systems[0].content == "Shared system instructions"
	)
	assert restored_conversation.messages[0].system_index == 0
	assert restored_conversation.messages[1].system_index == 0


def test_save_restore_invalid_file(tmp_path: str):
	"""Test restoring from an invalid file."""
	temp_path = UPath(f"{tmp_path}{os.sep}invalid_file.bskc")
	with temp_path.open("wb") as temp_file:
		temp_file.write(b"This is not a valid zip file")

	storage_path = UPath("memory://test_invalid_restore")
	with pytest.raises(zipfile.BadZipFile):
		Conversation.open(temp_path, storage_path)


def test_save_restore_with_image_attachment(tmp_path: str):
	"""Test saving and restoring a conversation with image attachments."""
	image_path = UPath(tmp_path) / "test_image.png"
	with image_path.open("wb") as f:
		img = Image.new('RGB', (100, 50), color='red')
		img.save(f, format='PNG')

	conversation = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")

	image_attachment = ImageFile(location=image_path)

	request = Message(
		role=MessageRoleEnum.USER,
		content="Test message with image",
		attachments=[image_attachment],
	)

	block = MessageBlock(request=request, model=model)
	conversation.add_block(block)

	bskc_path = tmp_path / "test_conversation.bskc"
	conversation.save(str(bskc_path))

	storage_path = UPath("memory://test_image_restore")
	restored_conversation = Conversation.open(str(bskc_path), storage_path)
	assert isinstance(restored_conversation, Conversation)
	assert len(restored_conversation.messages) == 1
	restored_attachment = restored_conversation.messages[0].request.attachments[
		0
	]
	assert isinstance(restored_attachment, ImageFile)
	assert restored_attachment.dimensions == (100, 50)
	assert restored_attachment.location.exists()


def test_save_restore_with_text_attachment(tmp_path: str):
	"""Test saving and restoring a conversation with text file attachments."""
	text_path = UPath(tmp_path) / "test_file.txt"
	with text_path.open("w") as f:
		f.write("This is a test file content")

	conversation = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")
	text_attachment = AttachmentFile(location=text_path)
	request = Message(
		role=MessageRoleEnum.USER,
		content="Test message with text file",
		attachments=[text_attachment],
	)

	block = MessageBlock(request=request, model=model)

	conversation.add_block(block)
	bskc_path = tmp_path / "test_conversation.bskc"
	conversation.save(str(bskc_path))

	storage_path = UPath("memory://test_text_restore")
	restored_conversation = Conversation.open(str(bskc_path), storage_path)
	assert isinstance(restored_conversation, Conversation)
	assert len(restored_conversation.messages) == 1
	restored_attachment = restored_conversation.messages[0].request.attachments[
		0
	]
	assert isinstance(restored_attachment, AttachmentFile)

	restored_file_path = restored_attachment.location
	assert restored_file_path.exists()

	with restored_file_path.open("r") as f:
		content = f.read()
		assert content == "This is a test file content"


def test_save_restore_with_url_attachment(tmp_path: str):
	"""Test saving and restoring a conversation with URL attachments."""
	conversation = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")
	url = "https://example.com/image.jpg"
	image = ImageFile(location=UPath(url))
	request = Message(
		role=MessageRoleEnum.USER,
		content="Test message with URL image",
		attachments=[image],
	)
	block = MessageBlock(request=request, model=model)
	conversation.add_block(block)
	bskc_path = tmp_path / "test_conversation.bskc"
	conversation.save(str(bskc_path))

	storage_path = UPath("memory://test_url_restore")
	restored_conversation = Conversation.open(str(bskc_path), storage_path)
	assert isinstance(restored_conversation, Conversation)
	assert len(restored_conversation.messages) == 1
	restored_attachment = restored_conversation.messages[0].request.attachments[
		0
	]
	assert isinstance(restored_attachment, ImageFile)
	assert str(restored_attachment.location) == url


def test_save_restore_with_multiple_attachments(tmp_path: str):
	"""Test saving and restoring a conversation with multiple attachments."""
	text_path = UPath(tmp_path) / "test_file.txt"
	with text_path.open("w") as f:
		f.write("This is a test file content")

	image_path = UPath(tmp_path) / "test_image.png"
	with image_path.open("wb") as f:
		img = Image.new('RGB', (100, 50), color='red')
		img.save(f, format='PNG')

	conversation = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")

	text_attachment = AttachmentFile(location=text_path)
	image_attachment = ImageFile(location=image_path)
	url_image = ImageFile(location=UPath("https://example.com/image.jpg"))

	request = Message(
		role=MessageRoleEnum.USER,
		content="Test message with multiple attachments",
		attachments=[text_attachment, image_attachment, url_image],
	)
	block = MessageBlock(request=request, model=model)
	conversation.add_block(block)

	bskc_path = tmp_path / "test_conversation.bskc"
	conversation.save(str(bskc_path))

	storage_path = UPath("memory://test_multiple_restore")
	restored_conversation = Conversation.open(str(bskc_path), storage_path)
	assert isinstance(restored_conversation, Conversation)
	assert len(restored_conversation.messages) == 1
	restored_attachments = restored_conversation.messages[0].request.attachments
	assert len(restored_attachments) == 3
	assert isinstance(restored_attachments[0], AttachmentFile)
	assert isinstance(restored_attachments[1], ImageFile)
	assert isinstance(restored_attachments[2], ImageFile)
	assert restored_attachments[0].location.exists()
	assert restored_attachments[1].location.exists()
	assert (
		str(restored_attachments[2].location) == "https://example.com/image.jpg"
	)


def test_save_conversation_with_citations(tmp_path: str):
	"""Test saving and restoring a conversation with citations."""
	conversation = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="test_model")
	citations = [
		{"text": "Citation 1", "source": "Source 1", "page": 42},
		{
			"text": "Citation 2",
			"source": "Source 2",
			"url": "https://example.com",
		},
	]

	request = Message(role=MessageRoleEnum.USER, content="Test message")
	response = Message(
		role=MessageRoleEnum.ASSISTANT,
		content="Test response with citations",
		citations=citations,
	)
	block = MessageBlock(request=request, response=response, model=model)

	conversation.add_block(block)
	temp_path = f"{tmp_path}{os.sep}test_conversation.bskc"
	conversation.save(temp_path)

	storage_path = UPath("memory://test_citation_restore")
	restored_conversation = Conversation.open(temp_path, storage_path)
	assert isinstance(restored_conversation, Conversation)
	assert len(restored_conversation.messages) == 1
	restored_citations = restored_conversation.messages[0].response.citations
	assert len(restored_citations) == 2
	assert restored_citations[0]["text"] == "Citation 1"
	assert restored_citations[0]["source"] == "Source 1"
	assert restored_citations[0]["page"] == 42
	assert restored_citations[1]["text"] == "Citation 2"
	assert restored_citations[1]["source"] == "Source 2"
	assert restored_citations[1]["url"] == "https://example.com"
