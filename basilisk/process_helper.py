"""Helper functions for running tasks in separate processes."""

from __future__ import annotations

import multiprocessing
from typing import TYPE_CHECKING, Any, Callable

from .multiprocessing_worker import start_worker_process

if TYPE_CHECKING:
	from multiprocessing import Queue


def run_task(
	task: Callable, result_queue: Queue, cancel_flag, *args: Any, **kwargs: Any
) -> multiprocessing.Process:
	"""Run a task in a separate process.

	Args:
		task: The task to run
		result_queue: The queue to store the task result
		cancel_flag: The flag to indicate if the task should be cancelled
		*args: The task arguments
		**kwargs: The task keyword arguments

	Returns:
		The started process
	"""
	return start_worker_process(
		task, result_queue, cancel_flag, *args, **kwargs
	)
