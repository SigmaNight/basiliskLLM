"""Logging utilities for Basilisk application."""

import logging
import sys
from pathlib import Path
from types import TracebackType
from typing import Type

from platformdirs import user_log_path

import basilisk.global_vars as global_vars
from basilisk.consts import APP_AUTHOR, APP_NAME


def get_log_file_path() -> Path:
	"""Get log file path for Basilisk application.

	The path is determined by:
	- user_data_path if configured
	- platformdirs.user_log_path() otherwise

	Returns:
		The path to the log file depending on the configuration
	"""
	log_file_path = Path("basilisk.log")
	if global_vars.user_data_path:
		log_file_path = global_vars.user_data_path / log_file_path
	else:
		log_file_path = (
			user_log_path(APP_NAME, APP_AUTHOR, ensure_exists=True)
			/ log_file_path
		)
	return log_file_path


def setup_logging(level: str) -> None:
	"""Setup logging configuration for Basilisk.

	Configures logging to write to a file and optionally to the console as well.
	Configure the format of the log messages and the logging level.

	Args:
		level: logging level to set. 'OFF' is converted to 'NOTSET'.
	"""
	level = level.upper()
	if level == "OFF":
		level = "NOTSET"
	handlers = [logging.FileHandler(get_log_file_path(), mode='w')]
	if not getattr(sys, "frozen", False):
		handlers.append(logging.StreamHandler())
	logging.basicConfig(
		level=level,
		format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
		handlers=handlers,
		force=True,
	)


def set_log_level(level: str) -> None:
	"""Change global log level to new level and update all loggers accordingly.

	Args:
		level: new log level
	"""
	cur_level = logging.getLevelName(logging.root.getEffectiveLevel())
	if cur_level == level:
		return
	logging.root.setLevel(level)
	for handler in logging.root.handlers:
		handler.setLevel(level)
	new_level = logging.getLevelName(logging.root.getEffectiveLevel())
	logging.root.debug(f"Log level changed from {cur_level} to {new_level}")


def logging_uncaught_exceptions(
	exc_type: Type[Exception],
	exc_value: Exception,
	exc_traceback: TracebackType,
) -> None:
	"""Log uncaught exceptions to the appropriate logger.

	Args:
		exc_type: exception type is an exception class
		exc_value: exception value is an exception instance
		exc_traceback: exception traceback is a traceback object
	"""
	if isinstance(exc_type, KeyboardInterrupt):
		logging.info("Keyboard interrupt")
		return
	logging.getLogger(exc_type.__module__).error(
		"Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
	)
