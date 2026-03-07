"""Orchestrates completions and voice sessions for presenters."""

from __future__ import annotations

import logging
from typing import Any, Optional

import wx

from basilisk.completion_handler import CompletionHandler
from basilisk.provider_engine.voice_session import (
	BaseVoiceSession,
	VoiceSessionCallbacks,
	VoiceSessionConfig,
)
from basilisk.services.async_loop_runner import AsyncLoopRunner

log = logging.getLogger(__name__)


class ConversationOrchestrator:
	"""Service to manage completion and voice sessions."""

	def __init__(
		self,
		on_completion_start=None,
		on_completion_end=None,
		on_stream_chunk=None,
		on_stream_start=None,
		on_stream_finish=None,
		on_non_stream_finish=None,
		on_error=None,
		on_voice_status=None,
		on_voice_user_text=None,
		on_voice_assistant_text=None,
		on_voice_audio_chunk=None,
		on_voice_error=None,
	) -> None:
		"""Initialize orchestrator with completion and voice session callbacks."""
		self._completion_handler = CompletionHandler(
			on_completion_start=on_completion_start,
			on_completion_end=on_completion_end,
			on_stream_chunk=on_stream_chunk,
			on_stream_start=on_stream_start,
			on_stream_finish=on_stream_finish,
			on_non_stream_finish=on_non_stream_finish,
			on_error=on_error,
		)
		self._async_runner = AsyncLoopRunner("VoiceAsyncLoop")
		self._voice_session: Optional[BaseVoiceSession] = None
		self._voice_task: Optional[Any] = None

		self._voice_callbacks = VoiceSessionCallbacks(
			on_status=self._wrap_call_after(on_voice_status),
			on_user_text=self._wrap_call_after(on_voice_user_text),
			on_assistant_text=self._wrap_call_after(on_voice_assistant_text),
			on_audio_chunk=self._wrap_call_after(on_voice_audio_chunk),
			on_error=self._wrap_call_after(on_voice_error),
		)

	@staticmethod
	def _wrap_call_after(callback):
		if callback is None:
			return None

		def _wrapped(*args, **kwargs):
			wx.CallAfter(callback, *args, **kwargs)

		return _wrapped

	def start_completion(self, **kwargs: dict[str, Any]) -> None:
		"""Start a completion request via the completion handler."""
		self._completion_handler.start_completion(**kwargs)

	def stop_completion(self, skip_callbacks: bool = False) -> None:
		"""Stop the active completion request."""
		self._completion_handler.stop_completion(skip_callbacks=skip_callbacks)

	def is_completion_running(self) -> bool:
		"""Return True if a completion is currently in progress."""
		return self._completion_handler.is_running()

	def is_running(self) -> bool:
		"""Compatibility alias for completion running state."""
		return self.is_completion_running()

	def start_voice_session(self, engine, config: VoiceSessionConfig) -> None:
		"""Create and start a voice session for the given engine."""
		if self._voice_session:
			self.stop_voice_session()
		self._async_runner.start()
		self._voice_session = engine.create_voice_session(
			config=config, callbacks=self._voice_callbacks
		)
		self._voice_task = self._async_runner.submit(
			self._voice_session.start()
		)
		self._voice_task.add_done_callback(self._on_voice_task_done)

	def stop_voice_session(self) -> None:
		"""Stop the active voice session and shut down the async runner."""
		if not self._voice_session:
			return
		try:
			future = self._async_runner.submit(self._voice_session.stop())
			future.result(timeout=2)
		except Exception:
			log.debug("Failed to stop voice session", exc_info=True)
		self._voice_session = None
		self._voice_task = None
		self._async_runner.stop()

	def is_voice_running(self) -> bool:
		"""Return True if a voice session is currently active."""
		return self._voice_session is not None

	def _on_voice_task_done(self, task) -> None:
		if task.cancelled():
			log.debug("Voice session task cancelled")
		else:
			try:
				task.result()
			except Exception:
				log.debug("Voice session task failed", exc_info=True)
		self._voice_session = None
		self._voice_task = None
		self._async_runner.stop()

	def cleanup(self) -> None:
		"""Stop completion and voice session."""
		if self.is_completion_running():
			self.stop_completion(skip_callbacks=True)
		if self.is_voice_running():
			self.stop_voice_session()
