"""Tests for ConversationHistoryPresenter."""

from unittest.mock import MagicMock

import pytest

from basilisk.presenters.conversation_history_presenter import (
	ConversationHistoryPresenter,
)


@pytest.fixture
def mock_conv_db():
	"""Return a mock ConversationDatabase."""
	return MagicMock()


@pytest.fixture
def presenter(mock_conv_db):
	"""Return a ConversationHistoryPresenter with a mock DB getter."""
	view = MagicMock()
	return ConversationHistoryPresenter(
		view, conv_db_getter=lambda: mock_conv_db
	)


class TestLoadConversations:
	"""Tests for ConversationHistoryPresenter.load_conversations."""

	def test_delegates_to_db(self, presenter, mock_conv_db):
		"""load_conversations should call list_conversations on the DB."""
		expected = [{"id": 1, "title": "Test"}]
		mock_conv_db.list_conversations.return_value = expected

		result = presenter.load_conversations()

		mock_conv_db.list_conversations.assert_called_once_with(
			search=None, limit=200
		)
		assert result == expected

	def test_passes_search_string(self, presenter, mock_conv_db):
		"""load_conversations should forward the search parameter."""
		mock_conv_db.list_conversations.return_value = []

		presenter.load_conversations(search="hello", limit=50)

		mock_conv_db.list_conversations.assert_called_once_with(
			search="hello", limit=50
		)

	def test_returns_empty_list_on_error(self, presenter, mock_conv_db):
		"""load_conversations should return [] when the DB raises."""
		mock_conv_db.list_conversations.side_effect = RuntimeError("DB error")

		result = presenter.load_conversations()

		assert result == []


class TestDeleteConversation:
	"""Tests for ConversationHistoryPresenter.delete_conversation."""

	def test_returns_true_on_success(self, presenter, mock_conv_db):
		"""delete_conversation should return True when the DB call succeeds."""
		result = presenter.delete_conversation(42)

		mock_conv_db.delete_conversation.assert_called_once_with(42)
		assert result is True

	def test_returns_false_on_error(self, presenter, mock_conv_db):
		"""delete_conversation should return False when the DB raises."""
		mock_conv_db.delete_conversation.side_effect = RuntimeError("DB error")

		result = presenter.delete_conversation(42)

		assert result is False
