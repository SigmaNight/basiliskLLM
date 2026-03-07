"""Tests for ConversationOrchestrator service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from basilisk.provider_engine.voice_session import VoiceSessionConfig
from basilisk.services.conversation_orchestrator import ConversationOrchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orchestrator(**kwargs) -> ConversationOrchestrator:
	"""Return a ConversationOrchestrator with mocked CompletionHandler."""
	with patch("basilisk.services.conversation_orchestrator.CompletionHandler"):
		orch = ConversationOrchestrator(**kwargs)
	return orch


def _make_config() -> VoiceSessionConfig:
	"""Return a minimal VoiceSessionConfig."""
	return VoiceSessionConfig(model="gpt-realtime", voice="marin")


# ---------------------------------------------------------------------------
# _wrap_call_after
# ---------------------------------------------------------------------------


class TestWrapCallAfter:
	"""Tests for ConversationOrchestrator._wrap_call_after."""

	def test_none_callback_returns_none(self):
		"""_wrap_call_after(None) returns None."""
		assert ConversationOrchestrator._wrap_call_after(None) is None

	def test_wraps_callback_with_call_after(self):
		"""_wrap_call_after returns a function that invokes wx.CallAfter."""
		fn = MagicMock()
		wrapped = ConversationOrchestrator._wrap_call_after(fn)
		assert wrapped is not None
		with patch(
			"basilisk.services.conversation_orchestrator.wx.CallAfter"
		) as mock_ca:
			wrapped("hello", key="val")
			mock_ca.assert_called_once_with(fn, "hello", key="val")

	def test_wrapped_function_is_distinct_from_original(self):
		"""The wrapped function is not the same object as the original."""
		fn = MagicMock()
		wrapped = ConversationOrchestrator._wrap_call_after(fn)
		assert wrapped is not fn


# ---------------------------------------------------------------------------
# Completion delegation
# ---------------------------------------------------------------------------


class TestCompletionDelegation:
	"""Tests that completion methods delegate to CompletionHandler."""

	def test_start_completion_delegates(self):
		"""start_completion() calls handler.start_completion with kwargs."""
		orch = _make_orchestrator()
		orch._completion_handler.start_completion = MagicMock()
		orch.start_completion(engine=MagicMock(), conversation=MagicMock())
		orch._completion_handler.start_completion.assert_called_once()

	def test_stop_completion_delegates(self):
		"""stop_completion() calls handler.stop_completion."""
		orch = _make_orchestrator()
		orch._completion_handler.stop_completion = MagicMock()
		orch.stop_completion()
		orch._completion_handler.stop_completion.assert_called_once_with(
			skip_callbacks=False
		)

	def test_stop_completion_skip_callbacks(self):
		"""stop_completion(skip_callbacks=True) passes flag to handler."""
		orch = _make_orchestrator()
		orch._completion_handler.stop_completion = MagicMock()
		orch.stop_completion(skip_callbacks=True)
		orch._completion_handler.stop_completion.assert_called_once_with(
			skip_callbacks=True
		)

	def test_is_completion_running_delegates(self):
		"""is_completion_running() returns handler.is_running()."""
		orch = _make_orchestrator()
		orch._completion_handler.is_running = MagicMock(return_value=True)
		assert orch.is_completion_running() is True
		orch._completion_handler.is_running.return_value = False
		assert orch.is_completion_running() is False

	def test_is_running_alias(self):
		"""is_running() is an alias for is_completion_running()."""
		orch = _make_orchestrator()
		orch._completion_handler.is_running = MagicMock(return_value=True)
		assert orch.is_running() is True


# ---------------------------------------------------------------------------
# Voice session methods
# ---------------------------------------------------------------------------


class TestVoiceSessionMethods:
	"""Tests for voice session start/stop/is_running."""

	def test_is_voice_running_initially_false(self):
		"""No active voice session on construction."""
		orch = _make_orchestrator()
		assert orch.is_voice_running() is False

	def test_start_voice_session_sets_session(self):
		"""start_voice_session() creates and stores the voice session."""
		orch = _make_orchestrator()
		mock_session = MagicMock()
		mock_session.start = MagicMock(return_value=MagicMock())
		engine = MagicMock()
		engine.create_voice_session.return_value = mock_session
		mock_future = MagicMock()
		orch._async_runner = MagicMock()
		orch._async_runner.submit.return_value = mock_future

		orch.start_voice_session(engine=engine, config=_make_config())

		assert orch._voice_session is mock_session
		assert orch.is_voice_running() is True
		orch._async_runner.start.assert_called_once()
		orch._async_runner.submit.assert_called_once()
		mock_future.add_done_callback.assert_called_once()

	def test_start_voice_session_stops_existing_first(self):
		"""start_voice_session() stops any running session first."""
		orch = _make_orchestrator()
		orch._voice_session = MagicMock()
		orch._async_runner = MagicMock()
		orch._async_runner.submit.return_value = MagicMock()
		orch.stop_voice_session = MagicMock()

		engine = MagicMock()
		engine.create_voice_session.return_value = MagicMock()
		orch.start_voice_session(engine=engine, config=_make_config())

		orch.stop_voice_session.assert_called_once()

	def test_stop_voice_session_when_none(self):
		"""stop_voice_session() is a no-op when no session is active."""
		orch = _make_orchestrator()
		orch._async_runner = MagicMock()
		orch.stop_voice_session()  # Should not raise
		orch._async_runner.submit.assert_not_called()

	def test_stop_voice_session_clears_state(self):
		"""stop_voice_session() clears session, task, and stops runner."""
		orch = _make_orchestrator()
		mock_session = MagicMock()
		mock_future = MagicMock()
		mock_future.result.return_value = None
		orch._voice_session = mock_session
		orch._voice_task = MagicMock()
		orch._async_runner = MagicMock()
		orch._async_runner.submit.return_value = mock_future

		orch.stop_voice_session()

		assert orch._voice_session is None
		assert orch._voice_task is None
		orch._async_runner.stop.assert_called_once()

	def test_stop_voice_session_handles_exception(self):
		"""stop_voice_session() continues even when future.result() raises."""
		orch = _make_orchestrator()
		orch._voice_session = MagicMock()
		mock_future = MagicMock()
		mock_future.result.side_effect = TimeoutError("timeout")
		orch._async_runner = MagicMock()
		orch._async_runner.submit.return_value = mock_future

		orch.stop_voice_session()  # Should not raise

		assert orch._voice_session is None
		orch._async_runner.stop.assert_called_once()


# ---------------------------------------------------------------------------
# _on_voice_task_done
# ---------------------------------------------------------------------------


class TestOnVoiceTaskDone:
	"""Tests for ConversationOrchestrator._on_voice_task_done."""

	def test_cancelled_task_clears_state(self):
		"""Cancelled task clears session and stops async runner."""
		orch = _make_orchestrator()
		orch._voice_session = MagicMock()
		orch._voice_task = MagicMock()
		orch._async_runner = MagicMock()
		task = MagicMock()
		task.cancelled.return_value = True

		orch._on_voice_task_done(task)

		assert orch._voice_session is None
		assert orch._voice_task is None
		orch._async_runner.stop.assert_called_once()

	def test_successful_task_clears_state(self):
		"""Successful task clears session and stops async runner."""
		orch = _make_orchestrator()
		orch._voice_session = MagicMock()
		orch._async_runner = MagicMock()
		task = MagicMock()
		task.cancelled.return_value = False
		task.result.return_value = None

		orch._on_voice_task_done(task)

		assert orch._voice_session is None
		orch._async_runner.stop.assert_called_once()

	def test_failed_task_clears_state_without_raising(self):
		"""Failed task clears session without propagating the exception."""
		orch = _make_orchestrator()
		orch._voice_session = MagicMock()
		orch._async_runner = MagicMock()
		task = MagicMock()
		task.cancelled.return_value = False
		task.result.side_effect = RuntimeError("crash")

		orch._on_voice_task_done(task)  # Should not raise

		assert orch._voice_session is None
		orch._async_runner.stop.assert_called_once()


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
	"""Tests for ConversationOrchestrator.cleanup()."""

	def test_cleanup_stops_running_completion(self):
		"""cleanup() stops completion when running."""
		orch = _make_orchestrator()
		orch._completion_handler.is_running = MagicMock(return_value=True)
		orch._completion_handler.stop_completion = MagicMock()
		orch._voice_session = None

		orch.cleanup()

		orch._completion_handler.stop_completion.assert_called_once_with(
			skip_callbacks=True
		)

	def test_cleanup_skips_stop_completion_when_idle(self):
		"""cleanup() does not call stop_completion when no completion is running."""
		orch = _make_orchestrator()
		orch._completion_handler.is_running = MagicMock(return_value=False)
		orch._completion_handler.stop_completion = MagicMock()
		orch._voice_session = None

		orch.cleanup()

		orch._completion_handler.stop_completion.assert_not_called()

	def test_cleanup_stops_voice_session_when_running(self):
		"""cleanup() stops active voice session."""
		orch = _make_orchestrator()
		orch._completion_handler.is_running = MagicMock(return_value=False)
		orch.stop_voice_session = MagicMock()
		orch._voice_session = MagicMock()  # is_voice_running() → True

		orch.cleanup()

		orch.stop_voice_session.assert_called_once()

	def test_cleanup_both_running(self):
		"""cleanup() stops both completion and voice session when both active."""
		orch = _make_orchestrator()
		orch._completion_handler.is_running = MagicMock(return_value=True)
		orch._completion_handler.stop_completion = MagicMock()
		orch.stop_voice_session = MagicMock()
		orch._voice_session = MagicMock()

		orch.cleanup()

		orch._completion_handler.stop_completion.assert_called_once_with(
			skip_callbacks=True
		)
		orch.stop_voice_session.assert_called_once()
