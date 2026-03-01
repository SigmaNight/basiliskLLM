"""Tests for ConversationService."""

from unittest.mock import MagicMock

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
def mock_sounds(mocker):
	"""Mock play_sound and stop_sound to prevent sound system init."""
	mocker.patch("basilisk.services.conversation_service.play_sound")
	mocker.patch("basilisk.services.conversation_service.stop_sound")


@pytest.fixture
def mock_config(mocker):
	"""Patch config used by ConversationService."""
	cfg = mocker.patch("basilisk.services.conversation_service.config")
	cfg.conf.return_value.conversation.auto_save_to_db = True
	return cfg


class TestAutoSaveToDb:
	"""Tests for auto_save_to_db."""

	@pytest.mark.parametrize(
		("is_private", "auto_save"),
		[(True, True), (False, False)],
		ids=["private", "config_off"],
	)
	def test_skips_auto_save(
		self, service, mock_conv_db, mock_config, is_private, auto_save
	):
		"""auto_save_to_db is skipped when private mode or config disables it."""
		service.private = is_private
		mock_config.conf.return_value.conversation.auto_save_to_db = auto_save
		conv = Conversation()
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		service.auto_save_to_db(conv, block)
		mock_conv_db.save_conversation.assert_not_called()

	def test_new_conversation_saves_full(
		self, service, mock_conv_db, conversation_with_block, mock_config
	):
		"""First auto-save should save the full conversation."""
		conv, block = conversation_with_block
		service.auto_save_to_db(conv, block)
		mock_conv_db.save_conversation.assert_called_once_with(conv)
		assert service.db_conv_id == 42

	def test_existing_conversation_saves_block(
		self, service, mock_conv_db, conversation_with_block, mock_config
	):
		"""Subsequent auto-save should save only the new block."""
		conv, block = conversation_with_block
		service.db_conv_id = 10
		service.auto_save_to_db(conv, block)
		mock_conv_db.save_message_block.assert_called_once()
		call_args = mock_conv_db.save_message_block.call_args
		assert call_args[0][0] == 10  # db_conv_id
		assert call_args[0][2] is block  # the block


class TestSaveConversation:
	"""Tests for save_conversation."""

	def test_saves_with_draft(self, service, tmp_path, mocker):
		"""Save should include draft block and then remove it."""
		conv = Conversation()
		draft = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="draft"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		file_path = str(tmp_path / "test.bskc")
		mocker.patch.object(Conversation, "save")
		success, error = service.save_conversation(conv, file_path, draft)
		assert success is True
		assert error is None
		# Draft should be temporarily appended then removed
		assert len(conv.messages) == 0

	def test_returns_error_on_failure(self, service, tmp_path, mocker):
		"""Save should return the exception on failure."""
		conv = Conversation()
		file_path = str(tmp_path / "test.bskc")
		exc = OSError("disk full")
		mocker.patch.object(Conversation, "save", side_effect=exc)
		success, error = service.save_conversation(conv, file_path)
		assert success is False
		assert error is exc


class TestSetPrivate:
	"""Tests for set_private."""

	@pytest.mark.parametrize(
		("db_conv_id", "expected_should_stop"),
		[(5, True), (None, False)],
		ids=["with_id", "no_id"],
	)
	def test_set_private_success(
		self, service, mock_conv_db, db_conv_id, expected_should_stop
	):
		"""Going private succeeds, deleting from DB if db_conv_id was set."""
		service.db_conv_id = db_conv_id
		success, should_stop = service.set_private(True)
		assert success is True
		assert should_stop is expected_should_stop
		if db_conv_id:
			mock_conv_db.delete_conversation.assert_called_once_with(db_conv_id)
		else:
			mock_conv_db.delete_conversation.assert_not_called()
		assert service.db_conv_id is None
		assert service.private is True

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
