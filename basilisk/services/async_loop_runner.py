"""Async loop runner for background asyncio tasks."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Coroutine, Optional

log = logging.getLogger(__name__)


class AsyncLoopRunner:
	"""Run an asyncio event loop in a dedicated thread."""

	def __init__(self, name: str = "AsyncLoopRunner") -> None:
		"""Initialize the runner with the given thread name."""
		self._name = name
		self._loop: Optional[asyncio.AbstractEventLoop] = None
		self._thread: Optional[threading.Thread] = None
		self._started = threading.Event()

	def start(self) -> None:
		"""Start the asyncio loop thread if not running."""
		if self._thread and self._thread.is_alive():
			return
		self._thread = threading.Thread(
			target=self._run_loop, name=self._name, daemon=True
		)
		self._thread.start()
		self._started.wait(timeout=2)

	def _run_loop(self) -> None:
		self._loop = asyncio.new_event_loop()
		asyncio.set_event_loop(self._loop)
		self._started.set()
		self._loop.run_forever()
		self._shutdown_loop()

	def _shutdown_loop(self) -> None:
		if not self._loop:
			return
		pending = asyncio.all_tasks(self._loop)
		for task in pending:
			task.cancel()
		if pending:
			self._loop.run_until_complete(
				asyncio.gather(*pending, return_exceptions=True)
			)
		self._loop.close()
		self._loop = None
		self._started.clear()

	def submit(self, coro: Coroutine) -> asyncio.Future:
		"""Submit a coroutine to the background event loop."""
		if not self._loop:
			raise RuntimeError("Async loop not started")
		return asyncio.run_coroutine_threadsafe(coro, self._loop)

	def stop(self) -> None:
		"""Stop the event loop and wait for the thread to exit."""
		if self._loop:
			self._loop.call_soon_threadsafe(self._loop.stop)
		if self._thread and self._thread.is_alive():
			if threading.current_thread() is self._thread:
				# Cannot join the current thread.
				return
			self._thread.join(timeout=1)
		self._thread = None
