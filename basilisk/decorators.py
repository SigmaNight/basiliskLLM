import logging
import time
from functools import wraps
from typing import Callable

import wx

logger = logging.getLogger(__name__)


def ensure_no_task_running(method: Callable):
	@wraps(method)
	def wrapper(instance, *args, **kwargs):
		if instance.task:
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
	@wraps(method)
	def wrapper(*args, **kwargs):
		start = time.time()
		result = method(*args, **kwargs)
		logger.debug(f"{method.__name__} took {time.time() - start} seconds")
		return result

	return wrapper
