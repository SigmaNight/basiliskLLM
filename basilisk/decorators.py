"""Decorators for the BasiliskLLM application.

This module provides decorators for:
- Task management: Ensuring sequential task execution
- Performance monitoring: Measuring method execution times
"""

import logging
import time
from functools import wraps
from typing import Callable

import wx

logger = logging.getLogger(__name__)


def ensure_no_task_running(method: Callable):
	"""Decorator to ensure no task is running before starting a new one.

	Checks if the instance has an active task (task.is_alive() is True) and displays an error message if attempting to start a new task while one is already running.

	Args:
		method: The method to decorate. The decorated method must be a member of a class with a 'task' attribute representing the running task.

	Returns:
		The decorated method that includes task running checks.
	"""

	@wraps(method)
	def wrapper(instance, *args, **kwargs):
		if instance.task is not None and instance.task.is_alive():
			logger.error("A task is already running.")
			wx.MessageBox(
				_("A task is already running. Please wait for it to complete."),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		return method(instance, *args, **kwargs)

	return wrapper


def measure_time(method: Callable):
	"""Decorator to measure the time taken by a method in seconds.

	Time measurement only occurs when debug logging is enabled. If debug logging is disabled, the method is called directly without timing.

	Args:
		method: The method to decorate (time measurement).

	Returns:
		The decorated method.

	Note:
		When debug logging is enabled, logs the execution time with format:
		"{module_name}.{qualname} took {seconds:.3f} seconds"
	"""

	@wraps(method)
	def wrapper(*args, **kwargs):
		if not logger.isEnabledFor(logging.DEBUG):
			return method(*args, **kwargs)
		start = time.time()
		module_name = method.__module__
		qualname = method.__qualname__
		result = method(*args, **kwargs)
		logger.debug(
			f"{module_name}.{qualname} took {time.time() - start:.3f} seconds"
		)
		return result

	return wrapper
