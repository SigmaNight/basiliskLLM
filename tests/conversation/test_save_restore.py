"""Unit tests for saving and restoring conversations."""

import json
import os
import zipfile

import pytest
from upath import UPath

from basilisk.consts import BSKC_VERSION
from basilisk.conversation import (
	AttachmentFile,
	Conversation,
	ImageFile,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)


class TestBasicSaveRestore:
	"""Tests for basic conversation save and restore functionality."""

	@pytest.fixture
	def bskc_path(self, tmp_path, request):
		"""Return a test conversation file path."""
		return f"{tmp_path}{os.sep}{request.node.name}.bskc"

	@pytest.fixture
	def storage_path(self, request):
		"""Return a test storage path."""
		return UPath("memory://{request.node.name}")

	def test_save_empty_conversation(self, empty_conversation, bskc_path):
		"""Test saving an empty conversation."""
		empty_conversation.save(bskc_path)

		assert os.path.exists(bskc_path)
		assert zipfile.is_zipfile(bskc_path)

		with zipfile.ZipFile(bskc_path, "r") as zip_file:
			assert "conversation.json" in zip_file.namelist()
			with zip_file.open("conversation.json") as json_file:
				data = json.load(json_file)
				assert data == {
					"messages": [],
					"systems": [],
					"title": None,
					"version": BSKC_VERSION,
				}

	def test_restore_empty_conversation(self, bskc_path, storage_path):
		"""Test restoring an empty conversation."""
		# Create a test conversation file
		with zipfile.ZipFile(bskc_path, "w") as zip_file:
			with zip_file.open("conversation.json", "w") as json_file:
				conv_data = {"messages": [], "systems": [], "title": None}
				conv_json = json.dumps(conv_data).encode("utf-8")
				json_file.write(conv_json)

		restored_conversation = Conversation.open(bskc_path, storage_path)

		assert isinstance(restored_conversation, Conversation)
		assert len(restored_conversation.messages) == 0
		assert len(restored_conversation.systems) == 0
		assert restored_conversation.title is None

	def test_save_restore_conversation_with_messages(
		self, empty_conversation, ai_model, bskc_path, storage_path
	):
		"""Test saving and restoring a conversation with messages."""
		# Setup conversation with messages
		empty_conversation.title = "Test Conversation"

		request1 = Message(role=MessageRoleEnum.USER, content="Test message 1")
		response1 = Message(
			role=MessageRoleEnum.ASSISTANT, content="Test response 1"
		)
		block1 = MessageBlock(
			request=request1, response=response1, model=ai_model
		)

		request2 = Message(role=MessageRoleEnum.USER, content="Test message 2")
		block2 = MessageBlock(request=request2, model=ai_model)

		empty_conversation.add_block(block1)
		empty_conversation.add_block(block2)

		# Save conversation
		empty_conversation.save(bskc_path)

		# Restore conversation
		restored_conversation = Conversation.open(bskc_path, storage_path)

		# Verify restored conversation
		assert isinstance(restored_conversation, Conversation)
		assert restored_conversation.title == "Test Conversation"
		assert len(restored_conversation.messages) == 2

		# Check first message
		assert (
			restored_conversation.messages[0].request.content
			== "Test message 1"
		)
		assert (
			restored_conversation.messages[0].response.content
			== "Test response 1"
		)
		assert restored_conversation.messages[0].model.provider_id == "openai"
		assert restored_conversation.messages[0].model.model_id == "test_model"

		# Check second message
		assert (
			restored_conversation.messages[1].request.content
			== "Test message 2"
		)
		assert restored_conversation.messages[1].response is None
		assert restored_conversation.messages[1].model.provider_id == "openai"

	def test_save_restore_invalid_file(self, tmp_path, storage_path):
		"""Test restoring from an invalid file."""
		# Create an invalid file
		temp_path = UPath(f"{tmp_path}{os.sep}invalid_file.bskc")
		with temp_path.open("wb") as temp_file:
			temp_file.write(b"This is not a valid zip file")

		with pytest.raises(zipfile.BadZipFile):
			Conversation.open(temp_path, storage_path)


class TestSystemMessageSaveRestore:
	"""Tests for saving and restoring conversations with system messages."""

	@pytest.fixture
	def bskc_path(self, tmp_path):
		"""Return a test conversation file path."""
		return f"{tmp_path}{os.sep}test_conversation.bskc"

	@pytest.fixture
	def storage_path(self):
		"""Return a test storage path."""
		return UPath("memory://test_system_restore")

	def test_save_restore_with_system_messages(
		self, empty_conversation, ai_model, bskc_path, storage_path
	):
		"""Test saving and restoring a conversation with system messages."""
		# Create system messages
		system1 = SystemMessage(
			role=MessageRoleEnum.SYSTEM, content="System instructions 1"
		)
		system2 = SystemMessage(
			role=MessageRoleEnum.SYSTEM, content="System instructions 2"
		)

		# Create message blocks
		request1 = Message(role=MessageRoleEnum.USER, content="Test message 1")
		block1 = MessageBlock(request=request1, model=ai_model)

		request2 = Message(role=MessageRoleEnum.USER, content="Test message 2")
		block2 = MessageBlock(request=request2, model=ai_model)

		# Add blocks with system messages
		empty_conversation.add_block(block1, system1)
		empty_conversation.add_block(block2, system2)

		# Save and restore conversation
		empty_conversation.save(bskc_path)
		restored_conversation = Conversation.open(bskc_path, storage_path)

		# Verify restored conversation
		assert isinstance(restored_conversation, Conversation)
		assert len(restored_conversation.systems) == 2
		assert (
			restored_conversation.systems[0].content == "System instructions 1"
		)
		assert (
			restored_conversation.systems[1].content == "System instructions 2"
		)
		assert restored_conversation.messages[0].system_index == 0
		assert restored_conversation.messages[1].system_index == 1

	def test_save_restore_with_shared_system_message(
		self, empty_conversation, ai_model, bskc_path, storage_path
	):
		"""Test saving and restoring a conversation with shared system messages."""
		# Create shared system message
		system = SystemMessage(
			role=MessageRoleEnum.SYSTEM, content="Shared system instructions"
		)

		# Create message blocks
		request1 = Message(role=MessageRoleEnum.USER, content="Test message 1")
		block1 = MessageBlock(request=request1, model=ai_model)

		request2 = Message(role=MessageRoleEnum.USER, content="Test message 2")
		block2 = MessageBlock(request=request2, model=ai_model)

		# Add blocks with the same system message
		empty_conversation.add_block(block1, system)
		empty_conversation.add_block(block2, system)

		# Save and restore conversation
		empty_conversation.save(bskc_path)
		restored_conversation = Conversation.open(bskc_path, storage_path)

		# Verify restored conversation
		assert isinstance(restored_conversation, Conversation)
		assert len(restored_conversation.systems) == 1
		assert (
			restored_conversation.systems[0].content
			== "Shared system instructions"
		)
		assert restored_conversation.messages[0].system_index == 0
		assert restored_conversation.messages[1].system_index == 0


class TestAttachmentSaveRestore:
	"""Tests for saving and restoring conversations with attachments."""

	@pytest.fixture
	def bskc_path(self, tmp_path):
		"""Return a test conversation file path."""
		return f"{tmp_path}{os.sep}test_conversation.bskc"

	@pytest.fixture
	def text_content(self):
		"""Return test text content."""
		return "This is a test file content"

	@pytest.fixture
	def text_path(self, tmp_path, text_content):
		"""Create and return a text file path."""
		path = UPath(tmp_path) / "test_file.txt"
		with path.open("w") as f:
			f.write(text_content)
		return path

	@pytest.fixture
	def text_attachment(self, text_path):
		"""Return a text file attachment."""
		return AttachmentFile(location=text_path)

	@pytest.fixture
	def url_image(self):
		"""Return a URL image attachment."""
		url = "https://example.com/image.jpg"
		return ImageFile(location=UPath(url))

	def test_save_restore_with_image_attachment(
		self, empty_conversation, ai_model, image_file, bskc_path
	):
		"""Test saving and restoring a conversation with image attachments."""
		# Create image attachment
		image_attachment = ImageFile(location=image_file)

		# Create message with image attachment
		request = Message(
			role=MessageRoleEnum.USER,
			content="Test message with image",
			attachments=[image_attachment],
		)

		# Add message to conversation
		block = MessageBlock(request=request, model=ai_model)
		empty_conversation.add_block(block)

		# Save conversation
		empty_conversation.save(str(bskc_path))

		# Restore conversation
		storage_path = UPath("memory://test_image_restore")
		restored_conversation = Conversation.open(str(bskc_path), storage_path)

		# Verify restored conversation
		assert isinstance(restored_conversation, Conversation)
		assert len(restored_conversation.messages) == 1

		# Verify restored attachment
		restored_attachment = restored_conversation.messages[
			0
		].request.attachments[0]
		assert isinstance(restored_attachment, ImageFile)
		assert restored_attachment.dimensions == (100, 50)
		assert restored_attachment.location.exists()

	def test_save_restore_with_text_attachment(
		self,
		empty_conversation,
		ai_model,
		text_attachment,
		text_content,
		bskc_path,
	):
		"""Test saving and restoring a conversation with text file attachments."""
		# Create message with text attachment
		request = Message(
			role=MessageRoleEnum.USER,
			content="Test message with text file",
			attachments=[text_attachment],
		)

		# Add message to conversation
		block = MessageBlock(request=request, model=ai_model)
		empty_conversation.add_block(block)

		# Save conversation
		empty_conversation.save(str(bskc_path))

		# Restore conversation
		storage_path = UPath("memory://test_text_restore")
		restored_conversation = Conversation.open(str(bskc_path), storage_path)

		# Verify restored conversation
		assert isinstance(restored_conversation, Conversation)
		assert len(restored_conversation.messages) == 1

		# Verify restored attachment
		restored_attachment = restored_conversation.messages[
			0
		].request.attachments[0]
		assert isinstance(restored_attachment, AttachmentFile)

		# Verify file exists and content
		restored_file_path = restored_attachment.location
		assert restored_file_path.exists()
		with restored_file_path.open("r") as f:
			content = f.read()
			assert content == text_content

	def test_save_restore_with_url_attachment(
		self, empty_conversation, ai_model, url_image, bskc_path
	):
		"""Test saving and restoring a conversation with URL attachments."""
		# Create message with URL attachment
		request = Message(
			role=MessageRoleEnum.USER,
			content="Test message with URL image",
			attachments=[url_image],
		)

		# Add message to conversation
		block = MessageBlock(request=request, model=ai_model)
		empty_conversation.add_block(block)

		# Save conversation
		empty_conversation.save(str(bskc_path))

		# Restore conversation
		storage_path = UPath("memory://test_url_restore")
		restored_conversation = Conversation.open(str(bskc_path), storage_path)

		# Verify restored conversation
		assert isinstance(restored_conversation, Conversation)
		assert len(restored_conversation.messages) == 1

		# Verify restored attachment
		restored_attachment = restored_conversation.messages[
			0
		].request.attachments[0]
		assert isinstance(restored_attachment, ImageFile)
		assert (
			str(restored_attachment.location) == "https://example.com/image.jpg"
		)

	def test_save_restore_with_multiple_attachments(
		self,
		empty_conversation,
		ai_model,
		text_attachment,
		image_attachment,
		url_image,
		bskc_path,
	):
		"""Test saving and restoring a conversation with multiple attachments."""
		# Create message with multiple attachments
		request = Message(
			role=MessageRoleEnum.USER,
			content="Test message with multiple attachments",
			attachments=[text_attachment, image_attachment, url_image],
		)

		# Add message to conversation
		block = MessageBlock(request=request, model=ai_model)
		empty_conversation.add_block(block)

		# Save conversation
		empty_conversation.save(str(bskc_path))

		# Restore conversation
		storage_path = UPath("memory://test_multiple_restore")
		restored_conversation = Conversation.open(str(bskc_path), storage_path)

		# Verify restored conversation
		assert isinstance(restored_conversation, Conversation)
		assert len(restored_conversation.messages) == 1

		# Verify restored attachments
		restored_attachments = restored_conversation.messages[
			0
		].request.attachments
		assert len(restored_attachments) == 3
		assert isinstance(restored_attachments[0], AttachmentFile)
		assert isinstance(restored_attachments[1], ImageFile)
		assert isinstance(restored_attachments[2], ImageFile)
		assert restored_attachments[0].location.exists()
		assert restored_attachments[1].location.exists()
		assert (
			str(restored_attachments[2].location)
			== "https://example.com/image.jpg"
		)

	def test_save_conversation_with_citations(
		self, empty_conversation, ai_model, bskc_path
	):
		"""Test saving and restoring a conversation with citations."""
		# Create citations
		citations = [
			{"text": "Citation 1", "source": "Source 1", "page": 42},
			{
				"text": "Citation 2",
				"source": "Source 2",
				"url": "https://example.com",
			},
		]

		# Create message with citations
		request = Message(role=MessageRoleEnum.USER, content="Test message")
		response = Message(
			role=MessageRoleEnum.ASSISTANT,
			content="Test response with citations",
			citations=citations,
		)

		# Add message to conversation
		block = MessageBlock(request=request, response=response, model=ai_model)
		empty_conversation.add_block(block)

		# Save conversation
		empty_conversation.save(bskc_path)

		# Restore conversation
		storage_path = UPath("memory://test_citation_restore")
		restored_conversation = Conversation.open(bskc_path, storage_path)

		# Verify restored conversation
		assert isinstance(restored_conversation, Conversation)
		assert len(restored_conversation.messages) == 1

		# Verify restored citations
		restored_citations = restored_conversation.messages[
			0
		].response.citations
		assert len(restored_citations) == 2
		assert restored_citations[0]["text"] == "Citation 1"
		assert restored_citations[0]["source"] == "Source 1"
		assert restored_citations[0]["page"] == 42
		assert restored_citations[1]["text"] == "Citation 2"
		assert restored_citations[1]["source"] == "Source 2"
		assert restored_citations[1]["url"] == "https://example.com"
