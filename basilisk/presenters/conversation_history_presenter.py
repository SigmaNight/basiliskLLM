"""Presenter for the conversation history dialog.

Extracts database access logic from ConversationHistoryDialog
into a wx-free presenter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
	from basilisk.conversation.database import ConversationDatabase

log = logging.getLogger(__name__)


class ConversationHistoryPresenter:
	"""Presenter for the conversation history dialog.

	Handles database queries for listing and deleting conversations,
	keeping the view free of direct database dependencies.

	Attributes:
		view: The ConversationHistoryDialog instance.
	"""

	def __init__(
		self, view, conv_db_getter: Callable[[], ConversationDatabase]
	) -> None:
		"""Initialize the presenter.

		Args:
			view: The dialog view.
			conv_db_getter: Callable that returns the ConversationDatabase
				singleton (deferred to avoid import-time wx dependency).
		"""
		self.view = view
		self._get_conv_db = conv_db_getter

	def load_conversations(
		self, search: str | None = None, limit: int = 200
	) -> list[dict]:
		"""Load conversations from the database.

		Args:
			search: Optional search string to filter conversations.
			limit: Maximum number of conversations to return.

		Returns:
			A list of conversation dicts, or an empty list on error.
		"""
		try:
			return self._get_conv_db().list_conversations(
				search=search, limit=limit
			)
		except Exception:
			log.error("Failed to load conversation list", exc_info=True)
			return []

	def delete_conversation(self, conv_id: int) -> bool:
		"""Delete a conversation from the database.

		Args:
			conv_id: The ID of the conversation to delete.

		Returns:
			True on success, False on error.
		"""
		try:
			self._get_conv_db().delete_conversation(conv_id)
			return True
		except Exception:
			log.error("Failed to delete conversation", exc_info=True)
			return False
