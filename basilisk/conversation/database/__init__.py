"""Database package for conversation persistence."""

import logging
from pathlib import Path

from basilisk import global_vars
from basilisk.consts import APP_AUTHOR, APP_NAME

from .manager import ConversationDatabase

log = logging.getLogger(__name__)


def get_db_path() -> Path:
	"""Determine the path for the conversation database file."""
	if global_vars.user_data_path:
		db_dir = global_vars.user_data_path
	else:
		from platformdirs import user_data_path

		db_dir = user_data_path(APP_NAME, APP_AUTHOR, ensure_exists=True)
	return db_dir / "conversations.db"


__all__ = ["ConversationDatabase", "get_db_path"]
