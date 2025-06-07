"""Common completion handling logic for conversation tab and edit dialog.

This module provides a shared completion handler that can be used by both
ConversationTab and EditBlockDialog to avoid code duplication. It supports
both streaming and non-streaming completion modes.
"""

from __future__ import annotations

import logging
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

if TYPE_CHECKING:
	from basilisk.provider_engine.base_engine import BaseEngine

logger = logging.getLogger(__name__)


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
		on_completion_result: Optional[Callable[[str], None]] = None,
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
			parent: The parent window for displaying error dialogs
			on_completion_start: Callback called when completion starts
			on_completion_end: Callback called when completion ends (success flag)
			on_stream_chunk: Callback called for each streaming chunk
			on_completion_result: Callback called with the final result
			on_error: Callback called when an error occurs
			on_stream_start: Callback called when streaming starts (new_block, system_message)
			on_stream_finish: Callback called when streaming finishes (new_block)
			on_non_stream_finish: Callback called when non-streaming finishes (new_block, system_message)
		"""
		self.on_completion_start = on_completion_start
		self.on_completion_end = on_completion_end
		self.on_stream_chunk = on_stream_chunk
		self.on_completion_result = on_completion_result
		self.on_error = on_error
		self.on_stream_start = on_stream_start
		self.on_stream_finish = on_stream_finish
		self.on_non_stream_finish = on_non_stream_finish
		self.task: Optional[threading.Thread] = None
		self._stop_completion = False
		self.last_time = 0

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
		self._stop_completion = False

		completion_args = {
			"engine": engine,
			"system_message": system_message,
			"conversation": conversation,
			"new_block": new_block,
			"stream": stream,
			**kwargs,
		}

		if self.on_completion_start:
			self.on_completion_start()

		self.task = threading.Thread(
			target=self._handle_completion, kwargs=completion_args
		)
		self.task.start()
		logger.debug(f"Completion task {self.task.ident} started")

	def stop_completion(self):
		"""Stop the current completion if running."""
		self._stop_completion = True
		if self.is_running():
			logger.debug(f"Stopping completion task {self.task.ident}")
			self.task.join(timeout=1)

	def is_running(self) -> bool:
		"""Check if a completion is currently running."""
		return self.task and self.task.is_alive()

	def _handle_completion(self, engine: BaseEngine, **kwargs: dict[str, Any]):
		"""Handle the completion request in a background thread.

		Args:
			engine: The engine to use for completion
			kwargs: The keyword arguments for the completion request
		"""
		try:
			play_sound("progress", loop=True)
			response = engine.completion(**kwargs)
		except Exception as e:
			logger.error("Error during completion", exc_info=True)
			wx.CallAfter(self._handle_error, str(e))
			return

		kwargs["engine"] = engine
		kwargs["response"] = response
		if kwargs.get("stream", False):
			self._handle_streaming_completion(**kwargs)
		else:
			self._handle_non_streaming_completion(**kwargs)

	def _handle_streaming_completion(
		self,
		engine: BaseEngine,
		response: Any,
		new_block: MessageBlock,
		system_message: Optional[SystemMessage],
		**kwargs: dict[str, Any],
	):
		"""Handle streaming completion response.

		Args:
			engine: The engine used for completion
			response: The completion response
			new_block: The message block being completed
			system_message: Optional system message
			kwargs: Additional completion arguments
		"""
		new_block.response = Message(role=MessageRoleEnum.ASSISTANT, content="")

		# Notify that streaming has started
		if self.on_stream_start:
			wx.CallAfter(self.on_stream_start, new_block, system_message)

		for chunk in engine.completion_response_with_stream(response):
			if self._stop_completion or global_vars.app_should_exit:
				logger.debug("Stopping completion")
				break

			if isinstance(chunk, str):
				new_block.response.content += chunk
				wx.CallAfter(self._handle_stream_chunk, chunk)
			elif isinstance(chunk, tuple):
				chunk_type, chunk_data = chunk
				if chunk_type == "citation":
					if not new_block.response.citations:
						new_block.response.citations = []
					new_block.response.citations.append(chunk_data)
				else:
					logger.warning(
						f"Unknown chunk type in streaming response: {chunk_type}"
					)

		# Notify that streaming has finished
		if self.on_stream_finish:
			wx.CallAfter(self.on_stream_finish, new_block)

		wx.CallAfter(
			self._completion_finished, new_block.response.content, True
		)

	def _handle_non_streaming_completion(
		self,
		engine: BaseEngine,
		response: Any,
		new_block: MessageBlock,
		system_message: Optional[SystemMessage],
		**kwargs: dict[str, Any],
	):
		"""Handle non-streaming completion response.

		Args:
			engine: The engine used for completion
			response: The completion response
			new_block: The message block being completed
			system_message: Optional system message
			kwargs: Additional completion arguments
		"""
		completed_block = engine.completion_response_without_stream(
			response=response, new_block=new_block, **kwargs
		)

		# Notify that non-streaming completion has finished
		if self.on_non_stream_finish:
			wx.CallAfter(
				self.on_non_stream_finish, completed_block, system_message
			)

		wx.CallAfter(
			self._completion_finished, completed_block.response.content, False
		)

	def _handle_stream_chunk(self, chunk: str):
		"""Handle a streaming chunk on the main thread.

		Args:
			chunk: The streaming chunk content
		"""
		if self.on_stream_chunk:
			self.on_stream_chunk(chunk)

		# Play periodic sound during streaming
		new_time = time.time()
		if new_time - self.last_time > 4:
			play_sound("chat_response_pending")
			self.last_time = new_time

	def _completion_finished(self, result: str, was_streaming: bool):
		"""Handle completion finish on the main thread.

		Args:
			result: The completion result content
			was_streaming: Whether this was a streaming completion
		"""
		stop_sound()
		if not was_streaming:
			play_sound("chat_response_received")

		if self.on_completion_result:
			self.on_completion_result(result)

		if self.on_completion_end:
			self.on_completion_end(True)

		self.task = None

	def _handle_error(self, error_message: str):
		"""Handle completion error on the main thread.

		Args:
			error_message: The error message
		"""
		stop_sound()

		if self.on_error:
			self.on_error(error_message)
		else:
			wx.MessageBox(
				_("An error occurred during completion: ") + error_message,
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)

		if self.on_completion_end:
			self.on_completion_end(False)

		self.task = None
