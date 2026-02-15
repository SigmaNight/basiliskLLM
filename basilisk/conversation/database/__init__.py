"""Database package for conversation persistence.

Provides singleton access to the conversation database via get_db() and
cleanup via close_db().
"""

import logging
from pathlib import Path

from basilisk import global_vars
from basilisk.consts import APP_AUTHOR, APP_NAME

from .manager import ConversationDatabase

log = logging.getLogger(__name__)

_db_instance: ConversationDatabase | None = None


def _get_db_path() -> Path:
	"""Determine the path for the conversation database file."""
	if global_vars.user_data_path:
		db_dir = global_vars.user_data_path
	else:
		from platformdirs import user_data_path

		db_dir = user_data_path(APP_NAME, APP_AUTHOR, ensure_exists=True)
	return db_dir / "conversations.db"


def get_db() -> ConversationDatabase:
	"""Get or create the singleton database instance.

	Returns:
		The ConversationDatabase singleton.
	"""
	global _db_instance
	if _db_instance is None:
		db_path = _get_db_path()
		_db_instance = ConversationDatabase(db_path)
	return _db_instance


def close_db():
	"""Close the database connection and release the singleton."""
	global _db_instance
	if _db_instance is not None:
		_db_instance.close()
		_db_instance = None
		log.debug("Database closed")
