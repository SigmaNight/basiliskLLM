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


def test_stale_worker_cleanup_preserves_newer_active_response(
	mocker, empty_conversation, message_block
):
	"""An old worker's finally block cannot clear a newer response."""
	processing_started = threading.Event()
	allow_old_worker_to_finish = threading.Event()
	old_response = object()
	new_response = object()
	old_engine = MagicMock()
	old_engine.completion.return_value = old_response

	def process_old_response(**kwargs):
		processing_started.set()
		assert allow_old_worker_to_finish.wait(timeout=1)
		return kwargs["new_block"]

	old_engine.completion_response_without_stream.side_effect = (
		process_old_response
	)
	mocker.patch("basilisk.completion_handler.play_sound")
	mocker.patch("basilisk.completion_handler.wx.CallAfter")
	handler = CompletionHandler()
	old_request = object()
	old_task = threading.Thread(
		target=handler._handle_completion,
		kwargs={
			"request": old_request,
			"engine": old_engine,
			"system_message": None,
			"conversation": empty_conversation,
			"new_block": message_block,
			"stream": False,
		},
	)
	with handler._completion_lock:
		handler._active_request = old_request
		handler.task = old_task
	old_task.start()
	assert processing_started.wait(timeout=1)

	new_request = object()
	new_engine = object()
	new_task = object()
	with handler._completion_lock:
		handler._active_request = new_request
		handler._active_engine = new_engine
		handler._active_response = new_response
		handler.task = new_task

	allow_old_worker_to_finish.set()
	old_task.join(timeout=1)
	assert not old_task.is_alive()
	assert handler._active_request is new_request
	assert handler._active_engine is new_engine
	assert handler._active_response is new_response
	assert handler.task is new_task


def test_stale_success_callback_does_not_finish_newer_completion(
	mocker, empty_conversation, message_block
):
	"""A queued success callback cannot clear a replacement worker."""
	queued_callbacks = []
	mocker.patch(
		"basilisk.completion_handler.wx.CallAfter",
		side_effect=lambda callback, *args: queued_callbacks.append(
			(callback, args)
		),
	)
	mocker.patch("basilisk.completion_handler.play_sound")
	mocker.patch("basilisk.completion_handler.stop_sound")
	completion_end = MagicMock()
	handler = CompletionHandler(on_completion_end=completion_end)
	first_engine = MagicMock()
	first_engine.completion.return_value = object()
	first_engine.completion_response_without_stream.side_effect = (
		lambda **kwargs: kwargs["new_block"]
	)

	handler.start_completion(
		engine=first_engine,
		system_message=None,
		conversation=empty_conversation,
		new_block=message_block,
	)
	first_task = handler.task
	assert first_task is not None
	first_task.join(timeout=1)
	assert not first_task.is_alive()
	assert len(queued_callbacks) == 1

	second_started = threading.Event()
	allow_second_completion = threading.Event()
	second_engine = MagicMock()

	def start_second_completion(**kwargs):
		second_started.set()
		assert allow_second_completion.wait(timeout=1)
		return object()

	second_engine.completion.side_effect = start_second_completion
	second_engine.completion_response_without_stream.side_effect = (
		lambda **kwargs: kwargs["new_block"]
	)
	handler.start_completion(
		engine=second_engine,
		system_message=None,
		conversation=empty_conversation,
		new_block=message_block,
	)
	assert second_started.wait(timeout=1)
	second_task = handler.task
	assert second_task is not None

	callback, args = queued_callbacks.pop(0)
	callback(*args)
	assert handler.task is second_task
	completion_end.assert_not_called()

	allow_second_completion.set()
	second_task.join(timeout=1)
	callback, args = queued_callbacks.pop(0)
	callback(*args)
	completion_end.assert_called_once_with(True)
	assert handler.task is None


def test_stale_error_callback_does_not_finish_newer_completion(
	mocker, empty_conversation, message_block
):
	"""A queued error callback cannot clear or fail a replacement worker."""
	queued_callbacks = []
	mocker.patch(
		"basilisk.completion_handler.wx.CallAfter",
		side_effect=lambda callback, *args: queued_callbacks.append(
			(callback, args)
		),
	)
	mocker.patch("basilisk.completion_handler.play_sound")
	mocker.patch("basilisk.completion_handler.stop_sound")
	completion_end = MagicMock()
	on_error = MagicMock()
	handler = CompletionHandler(
		on_completion_end=completion_end, on_error=on_error
	)
	first_engine = MagicMock()
	first_engine.completion.side_effect = RuntimeError("first failure")

	handler.start_completion(
		engine=first_engine,
		system_message=None,
		conversation=empty_conversation,
		new_block=message_block,
	)
	first_task = handler.task
	assert first_task is not None
	first_task.join(timeout=1)
	assert not first_task.is_alive()
	assert len(queued_callbacks) == 1

	second_started = threading.Event()
	allow_second_completion = threading.Event()
	second_engine = MagicMock()

	def start_second_completion(**kwargs):
		second_started.set()
		assert allow_second_completion.wait(timeout=1)
		return object()

	second_engine.completion.side_effect = start_second_completion
	second_engine.completion_response_without_stream.side_effect = (
		lambda **kwargs: kwargs["new_block"]
	)
	handler.start_completion(
		engine=second_engine,
		system_message=None,
		conversation=empty_conversation,
		new_block=message_block,
	)
	assert second_started.wait(timeout=1)
	second_task = handler.task
	assert second_task is not None

	callback, args = queued_callbacks.pop(0)
	callback(*args)
	assert handler.task is second_task
	on_error.assert_not_called()
	completion_end.assert_not_called()

	allow_second_completion.set()
	second_task.join(timeout=1)
	callback, args = queued_callbacks.pop(0)
	callback(*args)
	completion_end.assert_called_once_with(True)
	assert handler.task is None
