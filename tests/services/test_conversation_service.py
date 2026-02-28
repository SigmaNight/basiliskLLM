"""Tests for ConversationService."""

from unittest.mock import MagicMock, patch

import pytest

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.provider_ai_model import AIModelInfo
from basilisk.services.conversation_service import ConversationService


@pytest.fixture
def mock_conv_db():
	"""Return a mock ConversationDatabase."""
	db = MagicMock()
	db.save_conversation.return_value = 42
	return db


@pytest.fixture
def service(mock_conv_db):
	"""Return a ConversationService wired to a mock DB."""
	return ConversationService(conv_db_getter=lambda: mock_conv_db)


@pytest.fixture
def conversation_with_block():
	"""Return a conversation with one complete block."""
	conv = Conversation()
	req = Message(role=MessageRoleEnum.USER, content="Hello")
	resp = Message(role=MessageRoleEnum.ASSISTANT, content="Hi there!")
	block = MessageBlock(
		request=req,
		response=resp,
		model=AIModelInfo(provider_id="openai", model_id="test"),
	)
	conv.add_block(block)
	return conv, block


@pytest.fixture(autouse=True)
def mock_sounds():
	"""Mock play_sound and stop_sound to prevent sound system init."""
	with (
		patch("basilisk.services.conversation_service.play_sound") as mock_play,
		patch("basilisk.services.conversation_service.stop_sound") as mock_stop,
	):
		yield mock_play, mock_stop


class TestAutoSaveToDb:
	"""Tests for auto_save_to_db."""

	def test_skips_when_private(self, service, mock_conv_db):
		"""Auto-save should be skipped when private mode is enabled."""
		service.private = True
		conv = Conversation()
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		with patch("basilisk.services.conversation_service.config") as cfg:
			cfg.conf.return_value.conversation.auto_save_to_db = True
			service.auto_save_to_db(conv, block)
		mock_conv_db.save_conversation.assert_not_called()

	def test_skips_when_config_disabled(self, service, mock_conv_db):
		"""Auto-save should be skipped when config disables it."""
		conv = Conversation()
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		with patch("basilisk.services.conversation_service.config") as cfg:
			cfg.conf.return_value.conversation.auto_save_to_db = False
			service.auto_save_to_db(conv, block)
		mock_conv_db.save_conversation.assert_not_called()

	def test_new_conversation_saves_full(
		self, service, mock_conv_db, conversation_with_block
	):
		"""First auto-save should save the full conversation."""
		conv, block = conversation_with_block
		with patch("basilisk.services.conversation_service.config") as cfg:
			cfg.conf.return_value.conversation.auto_save_to_db = True
			service.auto_save_to_db(conv, block)
		mock_conv_db.save_conversation.assert_called_once_with(conv)
		assert service.db_conv_id == 42

	def test_existing_conversation_saves_block(
		self, service, mock_conv_db, conversation_with_block
	):
		"""Subsequent auto-save should save only the new block."""
		conv, block = conversation_with_block
		service.db_conv_id = 10
		with patch("basilisk.services.conversation_service.config") as cfg:
			cfg.conf.return_value.conversation.auto_save_to_db = True
			service.auto_save_to_db(conv, block)
		mock_conv_db.save_message_block.assert_called_once()
		call_args = mock_conv_db.save_message_block.call_args
		assert call_args[0][0] == 10  # db_conv_id
		assert call_args[0][2] is block  # the block


class TestSaveConversation:
	"""Tests for save_conversation."""

	def test_saves_with_draft(self, service, tmp_path):
		"""Save should include draft block and then remove it."""
		conv = Conversation()
		draft = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="draft"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		file_path = str(tmp_path / "test.bskc")
		with patch.object(Conversation, "save"):
			success, error = service.save_conversation(conv, file_path, draft)
		assert success is True
		assert error is None
		# Draft should be temporarily appended then removed
		assert len(conv.messages) == 0

	def test_returns_error_on_failure(self, service, tmp_path):
		"""Save should return the exception on failure."""
		conv = Conversation()
		file_path = str(tmp_path / "test.bskc")
		exc = OSError("disk full")
		with patch.object(Conversation, "save", side_effect=exc):
			success, error = service.save_conversation(conv, file_path)
		assert success is False
		assert error is exc


class TestSetPrivate:
	"""Tests for set_private."""

	def test_deletes_from_db(self, service, mock_conv_db):
		"""Going private should delete the conversation from DB."""
		service.db_conv_id = 5
		success, should_stop = service.set_private(True)
		assert success is True
		assert should_stop is True
		mock_conv_db.delete_conversation.assert_called_once_with(5)
		assert service.db_conv_id is None
		assert service.private is True

	def test_no_delete_when_no_db_id(self, service, mock_conv_db):
		"""Going private without a DB ID should not call delete."""
		success, should_stop = service.set_private(True)
		assert success is True
		assert should_stop is False
		mock_conv_db.delete_conversation.assert_not_called()

	def test_delete_failure_retains_id_and_reverts_flag(
		self, service, mock_conv_db
	):
		"""Failed DB deletion must not clear db_conv_id or set private."""
		service.db_conv_id = 7
		mock_conv_db.delete_conversation.side_effect = OSError("db error")
		success, should_stop = service.set_private(True)
		assert success is False
		assert should_stop is False
		assert service.db_conv_id == 7
		assert service.private is False


class TestGenerateTitle:
	"""Tests for generate_title."""

	def test_returns_content(self, service):
		"""generate_title should return the response content."""
		mock_engine = MagicMock()
		mock_response = MagicMock()
		mock_engine.completion.return_value = mock_response
		result_block = MagicMock()
		result_block.response.content = "My Title"
		mock_engine.completion_response_without_stream.return_value = (
			result_block
		)

		conv = Conversation()
		conv.add_block(
			MessageBlock(
				request=Message(role=MessageRoleEnum.USER, content="Hi"),
				response=Message(
					role=MessageRoleEnum.ASSISTANT, content="Hello"
				),
				model=AIModelInfo(provider_id="openai", model_id="test"),
			)
		)
		title = service.generate_title(
			engine=mock_engine,
			conversation=conv,
			provider_id="openai",
			model_id="test",
			temperature=0.5,
			top_p=1.0,
			max_tokens=100,
			stream=False,
		)
		assert title == "My Title"

	def test_returns_none_on_error(self, service):
		"""generate_title should return None on exception."""
		mock_engine = MagicMock()
		mock_engine.completion.side_effect = RuntimeError("API down")

		conv = Conversation()
		title = service.generate_title(
			engine=mock_engine,
			conversation=conv,
			provider_id="openai",
			model_id="test",
			temperature=0.5,
			top_p=1.0,
			max_tokens=100,
			stream=False,
		)
		assert title is None
