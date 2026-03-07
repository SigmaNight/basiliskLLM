"""Tests for AsyncLoopRunner background event loop management."""

from __future__ import annotations

import asyncio

import pytest

from basilisk.services.async_loop_runner import AsyncLoopRunner


class TestAsyncLoopRunnerStart:
	"""Tests for AsyncLoopRunner.start()."""

	def test_start_creates_thread_and_loop(self):
		"""start() spawns a daemon thread with a running event loop."""
		runner = AsyncLoopRunner(name="TestLoop")
		try:
			runner.start()
			assert runner._thread is not None
			assert runner._thread.is_alive()
			assert runner._loop is not None
			assert runner._loop.is_running()
		finally:
			runner.stop()

	def test_start_is_idempotent(self):
		"""Calling start() twice does not create a second thread."""
		runner = AsyncLoopRunner(name="TestLoop")
		try:
			runner.start()
			first_thread = runner._thread
			runner.start()
			assert runner._thread is first_thread
		finally:
			runner.stop()

	def test_thread_is_daemon(self):
		"""Background thread is a daemon thread."""
		runner = AsyncLoopRunner(name="TestLoop")
		try:
			runner.start()
			assert runner._thread.daemon is True
		finally:
			runner.stop()

	def test_thread_name(self):
		"""Thread name matches the name passed to the constructor."""
		runner = AsyncLoopRunner(name="MyLoop")
		try:
			runner.start()
			assert runner._thread.name == "MyLoop"
		finally:
			runner.stop()


class TestAsyncLoopRunnerStop:
	"""Tests for AsyncLoopRunner.stop()."""

	def test_stop_terminates_thread(self):
		"""stop() joins the thread so it is no longer alive."""
		runner = AsyncLoopRunner(name="TestLoop")
		runner.start()
		thread = runner._thread
		runner.stop()
		thread.join(timeout=2)
		assert not thread.is_alive()

	def test_stop_without_start_is_safe(self):
		"""stop() on an unstarted runner does not raise."""
		runner = AsyncLoopRunner(name="TestLoop")
		runner.stop()  # Should not raise


class TestAsyncLoopRunnerSubmit:
	"""Tests for AsyncLoopRunner.submit()."""

	def test_submit_runs_coroutine(self):
		"""submit() executes a coroutine and returns the result via a Future."""
		runner = AsyncLoopRunner(name="TestLoop")
		runner.start()
		try:

			async def _add(a, b):
				return a + b

			future = runner.submit(_add(2, 3))
			result = future.result(timeout=2)
			assert result == 5
		finally:
			runner.stop()

	def test_submit_propagates_exception(self):
		"""submit() propagates exceptions raised by the coroutine."""
		runner = AsyncLoopRunner(name="TestLoop")
		runner.start()
		try:

			async def _fail():
				raise ValueError("boom")

			future = runner.submit(_fail())
			with pytest.raises(ValueError, match="boom"):
				future.result(timeout=2)
		finally:
			runner.stop()

	def test_submit_without_start_raises(self):
		"""submit() raises RuntimeError when the loop has not been started."""
		runner = AsyncLoopRunner(name="TestLoop")

		async def _noop():
			pass

		coro = _noop()
		with pytest.raises(RuntimeError):
			runner.submit(coro)
		coro.close()  # prevent "coroutine was never awaited" warning

	def test_submit_concurrent_tasks(self):
		"""Multiple concurrent coroutines complete independently."""
		runner = AsyncLoopRunner(name="TestLoop")
		runner.start()
		try:
			results = []

			async def _task(n):
				await asyncio.sleep(0)
				return n * 2

			futures = [runner.submit(_task(i)) for i in range(5)]
			for i, f in enumerate(futures):
				results.append(f.result(timeout=2))
			assert sorted(results) == [0, 2, 4, 6, 8]
		finally:
			runner.stop()

	def test_restart_after_stop(self):
		"""Runner can be started again after being stopped."""
		runner = AsyncLoopRunner(name="TestLoop")
		runner.start()
		runner.stop()
		runner.start()
		try:

			async def _ping():
				return "pong"

			result = runner.submit(_ping()).result(timeout=2)
			assert result == "pong"
		finally:
			runner.stop()
