"""Helper functions for running tasks in separate processes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
	from multiprocessing import Queue


def run_task(
	task: Callable, result_queue: Queue, cancel_flag, *args: Any, **kwargs: Any
):
	"""Run a task in a separate process.

	Args:
		task: The task to run
		result_queue: The queue to store the task result
		cancel_flag: The flag to indicate if the task should be cancelled
		*args: The task arguments
		**kwargs: The task keyword arguments
	"""
	try:
		result = task(*args, **kwargs)
		result_queue.put(("result", result))
	except Exception as e:
		import traceback

		error_trace = traceback.format_exc()
		result_queue.put(("error", f"{str(e)}\n{error_trace}"))
