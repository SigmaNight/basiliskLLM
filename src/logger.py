import logging
import sys
from pathlib import Path
from types import TracebackType
from typing import Type
from platformdirs import user_log_path

log_file_path = Path("basilisk.log")
if getattr(sys, "frozen", False):
	log_file_path = (
		user_log_path("basilisk", "basilisk_llm", ensure_exists=True)
		/ log_file_path
	)


def setup_logging(level: str) -> None:
	"""Setup logging configuration"""
	console_handler = logging.StreamHandler()
	file_handler = logging.FileHandler(log_file_path, mode='w')
	logging.basicConfig(
		level=level,
		format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
		handlers=[console_handler, file_handler],
		force=True,
	)


def set_log_level(level: str) -> None:
	"""Change global log level to new level and update all loggers
	:param level: new log level
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
	"""Log uncaught exceptions"""
	if isinstance(exc_type, KeyboardInterrupt):
		logging.info("Keyboard interrupt")
		sys.__excepthook__
		return
	logging.getLogger(exc_type.__module__).error(
		"Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
	)
