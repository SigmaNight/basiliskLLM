"""Multiprocessing worker functions for cx_Freeze compatibility.

This module contains worker functions that are called by separate processes.
Having them in a separate module ensures they can be properly imported
by child processes when the application is frozen with cx_Freeze.
"""

from __future__ import annotations

import logging
import multiprocessing
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
	from multiprocessing import Queue


def setup_worker_logging(log_level: str) -> None:
	"""Set up logging for worker processes.

	Args:
		log_level: The logging level to set
	"""
	# Configure logging for the worker process
	level = getattr(logging, log_level.upper(), logging.INFO)
	logging.basicConfig(
		level=level,
		format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
	)


def run_task_worker(
	task: Callable, result_queue: Queue, cancel_flag, *args: Any, **kwargs: Any
) -> None:
	"""Run a task in a separate process.

	Args:
		task: The task to run
		result_queue: The queue to store the task result
		cancel_flag: The flag to indicate if the task should be cancelled
		*args: The task arguments
		**kwargs: The task keyword arguments
	"""
	try:
		# Set up logging if log_level is provided
		if "log_level" in kwargs:
			setup_worker_logging(kwargs["log_level"])

		# Add required parameters to kwargs
		kwargs["result_queue"] = result_queue
		kwargs["cancel_flag"] = cancel_flag

		# Execute the task
		result = task(*args, **kwargs)

		# Return result if not cancelled
		if not cancel_flag.value:
			result_queue.put(("result", result))
	except Exception as e:
		import traceback

		error_trace = traceback.format_exc()
		result_queue.put(("error", f"{str(e)}\n{error_trace}"))


def start_worker_process(
	task: Callable, result_queue: Queue, cancel_flag, *args: Any, **kwargs: Any
) -> multiprocessing.Process:
	"""Start a worker process to run a task.

	Args:
		task: The task to run
		result_queue: The queue to store the task result
		cancel_flag: The flag to indicate if the task should be cancelled
		*args: The task arguments
		**kwargs: The task keyword arguments

	Returns:
		The started process
	"""
	process = multiprocessing.Process(
		target=run_task_worker,
		args=(task, result_queue, cancel_flag, *args),
		kwargs=kwargs,
	)
	process.daemon = True
	process.start()
	return process


# Required for cx_Freeze multiprocessing support
if __name__ == "__main__":
	multiprocessing.freeze_support()
