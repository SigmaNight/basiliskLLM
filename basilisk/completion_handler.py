"""Common completion handling logic for conversation tab and edit dialog.

This module provides a shared completion handler that can be used by both
ConversationTab and EditBlockDialog to avoid code duplication. It supports
both streaming and non-streaming completion modes.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Optional

import wx

from basilisk import global_vars
from basilisk.conversation.conversation_model import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.decorators import ensure_no_task_running
from basilisk.sound_manager import play_sound, stop_sound
from basilisk.views.enhanced_error_dialog import show_enhanced_error_dialog

if TYPE_CHECKING:
	from basilisk.provider_engine.base_engine import BaseEngine

logger = logging.getLogger(__name__)

COMMON_PATTERN = r"[\n;:.?!)»\"\]}]"
RE_STREAM_BUFFER = re.compile(rf".*{COMMON_PATTERN}.*")


class CompletionHandler:
	"""Handles completion requests for both streaming and non-streaming modes.

	This class provides a unified interface for handling AI completions that can be
	used by both ConversationTab and EditBlockDialog to avoid code duplication.
	"""

	def __init__(
		self,
		on_completion_start: Optional[Callable[[], None]] = None,
		on_completion_end: Optional[Callable[[bool], None]] = None,
		on_stream_chunk: Optional[Callable[[str], None]] = None,
		on_error: Optional[Callable[[str], None]] = None,
		on_stream_start: Optional[
			Callable[[MessageBlock, Optional[SystemMessage]], None]
		] = None,
		on_stream_finish: Optional[Callable[[MessageBlock], None]] = None,
		on_non_stream_finish: Optional[
			Callable[[MessageBlock, Optional[SystemMessage]], None]
		] = None,
	):
		"""Initialize the completion handler.

		Args:
			on_completion_start: Callback called when completion starts
			on_completion_end: Callback called when completion ends (success flag)
			on_stream_chunk: Callback called for each streaming chunk
			on_error: Callback called when an error occurs
			on_stream_start: Callback called when streaming starts (new_block, system_message)
			on_stream_finish: Callback called when streaming finishes (new_block)
			on_non_stream_finish: Callback called when non-streaming finishes (new_block, system_message)
		"""
		self.on_completion_start = on_completion_start
		self.on_completion_end = on_completion_end
		self.on_stream_chunk = on_stream_chunk
		self.on_error = on_error
		self.on_stream_start = on_stream_start
		self.on_stream_finish = on_stream_finish
		self.on_non_stream_finish = on_non_stream_finish
		self.task: Optional[threading.Thread] = None
		self._stop_completion = False
		self._completion_lock = threading.Lock()
		self._active_request: object | None = None
		self._latest_request: object | None = None
		self._active_engine: Optional[BaseEngine] = None
		self._active_response: Any = None
		self.last_time = 0
		self._stream_buffers: dict[object, str] = {}

	@ensure_no_task_running
	def start_completion(
		self,
		engine: BaseEngine,
		system_message: Optional[SystemMessage],
		conversation: Conversation,
		new_block: MessageBlock,
		stream: bool = False,
		**kwargs: Any,
	):
		"""Start a completion request.

		Args:
			engine: The engine to use for completion
			system_message: Optional system message
			conversation: The conversation context
			new_block: The message block to complete
			stream: Whether to use streaming mode
			**kwargs: Additional arguments for the completion
		"""
		request = object()
		completion_args = {
			"engine": engine,
			"system_message": system_message,
			"conversation": conversation,
			"new_block": new_block,
			"stream": stream,
			**kwargs,
		}
		start_notified = threading.Event()
		with self._completion_lock:
			self._stop_completion = False
			self._active_request = request
			self._latest_request = request
			self._active_engine = None
			self._active_response = None
			self._stream_buffers[request] = ""
			task = threading.Thread(
				target=self._handle_completion,
				kwargs={
					"request": request,
					"start_notified": start_notified,
					**completion_args,
				},
			)
			self.task = task
			task.start()

		try:
			if self.on_completion_start:
				self.on_completion_start()
		finally:
			start_notified.set()
		logger.debug("Completion task %s started", task.ident)

	def stop_completion(self, skip_callbacks: bool = False):
		"""Stop the current completion if running.

		Args:
			skip_callbacks: If True, skip calling completion end callbacks.
				Useful when cleaning up resources before destroying the tab.
		"""
		with self._completion_lock:
			task = self.task
			request = self._latest_request
			is_running = bool(task and task.is_alive())
			if is_running:
				self._stop_completion = True
				engine = self._active_engine
				response = self._active_response

		if is_running:
			logger.debug("Stopping completion task: %s", task.ident)
			if engine is not None and response is not None:
				self._cancel_response(engine, response)
			task.join(timeout=0.1)
			with self._completion_lock:
				if self.task is task and not task.is_alive():
					self.task = None
			stop_sound()
		if self.on_completion_end and not skip_callbacks:
			if request is None:
				wx.CallAfter(self.on_completion_end, False)
			else:
				wx.CallAfter(self._completion_stopped, request)

	def is_running(self) -> bool:
		"""Check if a completion is currently running."""
		with self._completion_lock:
			return bool(self.task and self.task.is_alive())

	def _cancel_response(self, engine: BaseEngine, response: Any) -> None:
		"""Close an active provider response without surfacing stop errors."""
		try:
			engine.cancel_completion(response)
		except Exception:
			logger.debug(
				"Provider response could not be closed cleanly", exc_info=True
			)

	def _is_stopping(self, request: object) -> bool:
		with self._completion_lock:
			return (
				self._stop_completion
				or self._active_request is not request
				or global_vars.app_should_exit
			)

	def _handle_completion(
		self,
		request: object,
		engine: BaseEngine,
		start_notified: threading.Event | None = None,
		**kwargs: dict[str, Any],
	):
		"""Handle the completion request in a background thread.

		Args:
			request: Identity of the worker handling this completion.
			engine: The engine to use for completion
			start_notified: Set after the completion-start callback returns.
			kwargs: The keyword arguments for the completion request
		"""
		try:
			try:
				play_sound("progress", loop=True)
				response = engine.completion(**kwargs)
			except Exception as e:
				if self._is_stopping(request):
					logger.debug("Completion request cancelled", exc_info=True)
					return
				logger.error("Error during completion", exc_info=True)
				wx.CallAfter(self._handle_error, request, str(e))
				return

			with self._completion_lock:
				is_active_request = self._active_request is request
				if is_active_request:
					self._active_engine = engine
					self._active_response = response
				should_stop = (
					self._stop_completion
					or global_vars.app_should_exit
					or not is_active_request
				)

			if should_stop:
				self._cancel_response(engine, response)
				return
			if start_notified is not None:
				start_notified.wait()
				if self._is_stopping(request):
					return

			handle_func = (
				self._handle_streaming_completion
				if kwargs.get("stream", False)
				else self._handle_non_streaming_completion
			)
			kwargs["engine"] = engine
			kwargs["response"] = response
			try:
				success = handle_func(request=request, **kwargs)
			except Exception as e:
				if self._is_stopping(request):
					logger.debug("Completion response cancelled", exc_info=True)
					return
				logger.error(
					"Error handling completion response", exc_info=True
				)
				wx.CallAfter(self._handle_error, request, str(e))
				return

			if success and not self._is_stopping(request):
				wx.CallAfter(self._completion_finished_success, request)
		finally:
			with self._completion_lock:
				self._stream_buffers.pop(request, None)
				if self._active_request is request:
					self._active_engine = None
					self._active_response = None
				if (
					self._stop_completion
					and self._active_request is request
					and self.task is threading.current_thread()
				):
					self.task = None
					self._active_request = None

	def _handle_stream_chunk(
		self,
		request: object,
		chunk: str | tuple[str, Any],
		message_block: MessageBlock,
	):
		with self._completion_lock:
			if (
				self._stop_completion
				or self._active_request is not request
				or global_vars.app_should_exit
			):
				return
			if isinstance(chunk, str):
				buffer = self._stream_buffers.get(request, "") + chunk
				self._stream_buffers[request] = buffer
			elif isinstance(chunk, tuple):
				chunk_type, chunk_data = chunk
				if chunk_type == "citation":
					if not message_block.response.citations:
						message_block.response.citations = []
					message_block.response.citations.append(chunk_data)
				else:
					logger.warning(
						"Unknown chunk type in streaming response: %s",
						chunk_type,
					)
				buffer = self._stream_buffers.get(request, "")
			else:
				buffer = self._stream_buffers.get(request, "")

		if RE_STREAM_BUFFER.match(buffer):
			self.flush_stream_buffer(request, message_block)

	def flush_stream_buffer(
		self, request: object, message_block: MessageBlock
	) -> None:
		"""Flush the stream buffer to the message block."""
		with self._completion_lock:
			if (
				self._stop_completion
				or self._active_request is not request
				or global_vars.app_should_exit
			):
				return
			buffer = self._stream_buffers.get(request, "")
			self._stream_buffers[request] = ""

		if buffer:
			message_block.response.content += buffer
			wx.CallAfter(self._handle_stream_buffer, request, buffer)

	def _handle_streaming_completion(
		self,
		request: object,
		engine: BaseEngine,
		response: Any,
		new_block: MessageBlock,
		system_message: Optional[SystemMessage],
		**kwargs: dict[str, Any],
	) -> bool:
		"""Handle streaming completion response.

		Args:
			request: Identity of the worker handling this completion.
			engine: The engine used for completion
			response: The completion response
			new_block: The message block being completed
			system_message: Optional system message
			kwargs: Additional completion arguments

		Returns:
			True if streaming was handled successfully, False if stopped
		"""
		new_block.response = Message(role=MessageRoleEnum.ASSISTANT, content="")

		# Notify that streaming has started
		if self.on_stream_start:
			wx.CallAfter(
				self._handle_stream_start, request, new_block, system_message
			)

		for chunk in engine.completion_response_with_stream(response):
			if self._is_stopping(request):
				logger.debug("Stopping completion")
				return False
			self._handle_stream_chunk(request, chunk, new_block)

		# Notify that streaming has finished
		self.flush_stream_buffer(request, new_block)
		if self.on_stream_finish:
			wx.CallAfter(self._handle_stream_finish, request, new_block)
		return True

	def _handle_non_streaming_completion(
		self,
		request: object,
		engine: BaseEngine,
		response: Any,
		new_block: MessageBlock,
		system_message: Optional[SystemMessage],
		**kwargs: dict[str, Any],
	) -> bool:
		"""Handle non-streaming completion response.

		Args:
			request: Identity of the worker handling this completion.
			engine: The engine used for completion
			response: The completion response
			new_block: The message block being completed
			system_message: Optional system message
			kwargs: Additional completion arguments

		Returns:
			True if non-streaming completion was handled successfully, False if stopped
		"""
		completed_block = engine.completion_response_without_stream(
			response=response, new_block=new_block, **kwargs
		)

		# Notify that non-streaming completion has finished
		if self.on_non_stream_finish:
			wx.CallAfter(
				self._handle_non_stream_finish,
				request,
				completed_block,
				system_message,
			)

		return True

	def _handle_stream_start(
		self,
		request: object,
		new_block: MessageBlock,
		system_message: Optional[SystemMessage],
	):
		"""Notify the UI that the owning stream has started."""
		if self._is_stopping(request):
			return
		if self.on_stream_start:
			self.on_stream_start(new_block, system_message)

	def _handle_stream_finish(self, request: object, new_block: MessageBlock):
		"""Notify the UI that the owning stream has finished."""
		if self._is_stopping(request):
			return
		if self.on_stream_finish:
			self.on_stream_finish(new_block)

	def _handle_non_stream_finish(
		self,
		request: object,
		completed_block: MessageBlock,
		system_message: Optional[SystemMessage],
	):
		"""Notify the UI that the owning non-streaming request finished."""
		if self._is_stopping(request):
			return
		if self.on_non_stream_finish:
			self.on_non_stream_finish(completed_block, system_message)

	def _handle_stream_buffer(self, request: object, buffer: str):
		"""Handle a streaming chunk on the main thread.

		Args:
			request: Identity of the worker that produced the buffer.
			buffer: The streaming buffer content
		"""
		if self._is_stopping(request):
			return

		if self.on_stream_chunk:
			self.on_stream_chunk(buffer)

		# Play periodic sound during streaming
		new_time = time.time()
		if new_time - self.last_time > 4:
			play_sound("chat_response_pending")
			self.last_time = new_time

	def _completion_finished_success(self, request: object):
		"""Handle completion finish in success on the main thread."""
		with self._completion_lock:
			if self._active_request is not request:
				return
			self.task = None
			self._active_request = None
			self._active_engine = None
			self._active_response = None
			self._stream_buffers.pop(request, None)
		stop_sound()
		play_sound("chat_response_received")
		if self.on_completion_end:
			self.on_completion_end(True)

	def _handle_error(self, request: object, error_message: str):
		"""Handle completion error on the main thread.

		Args:
			request: Identity of the worker that raised the error.
			error_message: The error message
		"""
		with self._completion_lock:
			if self._active_request is not request:
				return
			self.task = None
			self._active_request = None
			self._active_engine = None
			self._active_response = None
			self._stream_buffers.pop(request, None)

		stop_sound()

		if self.on_error:
			self.on_error(error_message)
		else:
			show_enhanced_error_dialog(
				parent=None,
				message=_("An error occurred during completion: %s")
				% error_message,
				title=_("Completion Error"),
				is_completion_error=True,
			)

		if self.on_completion_end:
			self.on_completion_end(False)

	def _completion_stopped(self, request: object):
		"""Notify the UI that the latest completion was stopped."""
		with self._completion_lock:
			if self._latest_request is not request:
				return
		if self.on_completion_end:
			self.on_completion_end(False)
