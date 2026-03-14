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
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Optional

import wx

from basilisk import global_vars
from basilisk.conversation.content_utils import (
	END_REASONING,
	START_BLOCK_REASONING,
	split_reasoning_and_content,
)
from basilisk.conversation.conversation_model import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.decorators import ensure_no_task_running
from basilisk.provider_engine.stream_chunk_type import StreamChunkType
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
		self.last_time = 0
		self.stream_buffer: str = ""
		self._stream_reasoning_started: bool = False

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
		logger.debug("Completion task %s started", self.task.ident)

	def stop_completion(self, skip_callbacks: bool = False):
		"""Stop the current completion if running.

		Args:
			skip_callbacks: If True, skip calling completion end callbacks.
				Useful when cleaning up resources before destroying the tab.
		"""
		if self.is_running():
			self._stop_completion = True
			logger.debug("Stopping completion task: %s", self.task.ident)
			self.task.join(timeout=0.05)
			self.task = None
		if self.on_completion_end and not skip_callbacks:
			wx.CallAfter(self.on_completion_end, False)

	def is_running(self) -> bool:
		"""Check if a completion is currently running."""
		return self.task and self.task.is_alive()

	def _handle_completion(self, engine: BaseEngine, **kwargs: dict[str, Any]):
		"""Handle the completion request in a background thread.

		Args:
			engine: The engine to use for completion
			kwargs: The keyword arguments for the completion request
		"""
		started_at = datetime.now()
		try:
			play_sound("progress", loop=True)
			response = engine.completion(**kwargs)
		except Exception as e:
			logger.error("Error during completion", exc_info=True)
			wx.CallAfter(self._handle_error, str(e))
			return

		# Request is fully sent when completion() returns (streaming: we have the stream)
		request_sent_at = (
			datetime.now() if kwargs.get("stream", False) else None
		)

		handle_func = (
			self._handle_streaming_completion
			if kwargs.get("stream", False)
			else self._handle_non_streaming_completion
		)
		kwargs["engine"] = engine
		kwargs["response"] = response
		kwargs["started_at"] = started_at
		kwargs["request_sent_at"] = request_sent_at
		try:
			success = handle_func(**kwargs)
		except Exception as e:
			logger.error("Error handling completion response", exc_info=True)
			wx.CallAfter(self._handle_error, str(e))
			return

		if success:
			wx.CallAfter(self._completion_finished_success)

	def _handle_stream_chunk(
		self, chunk: tuple[str, Any], message_block: MessageBlock
	) -> None:
		chunk_type, chunk_data = chunk
		if chunk_type == StreamChunkType.CITATION:
			cits = message_block.response.citations
			if cits is None:
				cits = []
				message_block.response.citations = cits
			cits.append(chunk_data)
			return
		if chunk_type == StreamChunkType.REASONING:
			message_block.response.reasoning = (
				message_block.response.reasoning or ""
			) + chunk_data
			if not self._stream_reasoning_started:
				self._stream_reasoning_started = True
				wx.CallAfter(
					self._handle_stream_buffer,
					f"{START_BLOCK_REASONING}\n{chunk_data}",
				)
			else:
				wx.CallAfter(self._handle_stream_buffer, chunk_data)
			return
		if chunk_type == StreamChunkType.CONTENT:
			if self._stream_reasoning_started:
				self._stream_reasoning_started = False
				message_block.response.content += chunk_data
				wx.CallAfter(
					self._handle_stream_buffer,
					f"\n{END_REASONING}\n\n{chunk_data}",
				)
			else:
				self.stream_buffer += chunk_data
				if RE_STREAM_BUFFER.match(self.stream_buffer):
					self.flush_stream_buffer(message_block)
			return
		logger.warning(
			"Unknown chunk type in streaming response: %s", chunk_type
		)

	def flush_stream_buffer(self, message_block: MessageBlock) -> None:
		"""Flush the stream buffer to the message block."""
		if self.stream_buffer:
			message_block.response.content += self.stream_buffer
			wx.CallAfter(self._handle_stream_buffer, self.stream_buffer)
			self.stream_buffer = ""

	def _split_reasoning_from_content(
		self, message_block: MessageBlock
	) -> None:
		"""Parse leading reasoning block (think tags or legacy fenced think) into fields."""
		if not message_block.response:
			return
		reasoning, content = split_reasoning_and_content(
			message_block.response.content
		)
		if reasoning is not None:
			message_block.response = message_block.response.model_copy(
				update={"reasoning": reasoning, "content": content}
			)

	def _handle_streaming_completion(
		self,
		engine: BaseEngine,
		response: Any,
		new_block: MessageBlock,
		system_message: Optional[SystemMessage],
		**kwargs: dict[str, Any],
	) -> bool:
		"""Handle streaming completion response.

		Args:
			engine: The engine used for completion
			response: The completion response
			new_block: The message block being completed
			system_message: Optional system message
			kwargs: Additional completion arguments

		Returns:
			True if streaming was handled successfully, False if stopped
		"""
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT, content="", reasoning=None
		)
		self._stream_reasoning_started = False

		if self.on_stream_start:
			wx.CallAfter(self.on_stream_start, new_block, system_message)

		first_token_at: datetime | None = None
		for chunk in engine.completion_response_with_stream(
			response, new_block
		):
			if first_token_at is None:
				first_token_at = datetime.now()
			if self._stop_completion or global_vars.app_should_exit:
				logger.debug("Stopping completion")
				return False
			self._handle_stream_chunk(chunk, new_block)

		self.flush_stream_buffer(new_block)
		if self._stream_reasoning_started:
			wx.CallAfter(self._handle_stream_buffer, f"\n{END_REASONING}\n\n")
		self._split_reasoning_from_content(new_block)
		started_at = kwargs.get("started_at")
		request_sent_at = kwargs.get("request_sent_at")
		if started_at is not None:
			from basilisk.conversation.conversation_model import ResponseTiming

			new_block.timing = ResponseTiming(
				started_at=started_at,
				request_sent_at=request_sent_at,
				first_token_at=first_token_at,
				finished_at=datetime.now(),
			)
		if self.on_stream_finish:
			wx.CallAfter(self.on_stream_finish, new_block)
		return True

	def _handle_non_streaming_completion(
		self,
		engine: BaseEngine,
		response: Any,
		new_block: MessageBlock,
		system_message: Optional[SystemMessage],
		**kwargs: dict[str, Any],
	) -> bool:
		"""Handle non-streaming completion response.

		Args:
			engine: The engine used for completion
			response: The completion response
			new_block: The message block being completed
			system_message: Optional system message
			kwargs: Additional completion arguments

		Returns:
			True if non-streaming completion was handled successfully, False if stopped
		"""
		from basilisk.conversation.conversation_model import ResponseTiming

		completed_block = engine.completion_response_without_stream(
			response=response, new_block=new_block, **kwargs
		)
		self._split_reasoning_from_content(completed_block)
		started_at = kwargs.get("started_at")
		if started_at is not None:
			completed_block.timing = ResponseTiming(
				started_at=started_at, finished_at=datetime.now()
			)

		if self.on_non_stream_finish:
			wx.CallAfter(
				self.on_non_stream_finish, completed_block, system_message
			)

		return True

	def _handle_stream_buffer(self, buffer: str):
		"""Handle a streaming chunk on the main thread.

		Args:
			buffer: The streaming buffer content
		"""
		if self.on_stream_chunk:
			self.on_stream_chunk(buffer)

		new_time = time.time()
		if new_time - self.last_time > 4:
			play_sound("chat_response_pending")
			self.last_time = new_time

	def _completion_finished_success(self):
		"""Handle completion finish in success on the main thread."""
		stop_sound()
		play_sound("chat_response_received")
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
			show_enhanced_error_dialog(
				parent=None,
				message=_("An error occurred during completion: %s")
				% error_message,
				title=_("Completion Error"),
				is_completion_error=True,
			)

		if self.on_completion_end:
			self.on_completion_end(False)

		self.task = None
