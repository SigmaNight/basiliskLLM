"""Tests for completion lifecycle and cancellation."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from basilisk.completion_handler import CompletionHandler


class _BlockingStream:
	"""A stream that stays blocked until the provider response is closed."""

	def __init__(self):
		self.read_started = threading.Event()
		self.closed = threading.Event()

	def __iter__(self):
		return self

	def __next__(self):
		self.read_started.set()
		if not self.closed.wait(timeout=2):
			raise TimeoutError("test stream was not cancelled")
		raise OSError("stream closed")

	def close(self):
		self.closed.set()


def test_stop_closes_blocked_provider_stream(
	mocker, empty_conversation, message_block
):
	"""Stop interrupts a stream without waiting for another server chunk."""
	stream = _BlockingStream()
	engine = MagicMock()
	engine.completion.return_value = stream
	engine.completion_response_with_stream.return_value = stream
	engine.cancel_completion.side_effect = lambda response: response.close()
	completion_end = MagicMock()
	on_error = MagicMock()
	mocker.patch(
		"basilisk.completion_handler.wx.CallAfter",
		side_effect=lambda callback, *args: callback(*args),
	)
	mocker.patch("basilisk.completion_handler.play_sound")
	stop_sound = mocker.patch("basilisk.completion_handler.stop_sound")
	handler = CompletionHandler(
		on_completion_end=completion_end, on_error=on_error
	)

	handler.start_completion(
		engine=engine,
		system_message=None,
		conversation=empty_conversation,
		new_block=message_block,
		stream=True,
	)
	assert stream.read_started.wait(timeout=1)
	assert handler.is_running()
	assert handler._active_response is stream

	handler.stop_completion()

	engine.cancel_completion.assert_called_once_with(stream)
	assert stream.closed.wait(timeout=1)
	assert not handler.is_running()
	stop_sound.assert_called_once_with()
	completion_end.assert_called_once_with(False)
	on_error.assert_not_called()
