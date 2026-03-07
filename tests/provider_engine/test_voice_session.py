"""Tests for voice session classes and event dispatch logic."""

from __future__ import annotations

import asyncio
import base64
from unittest.mock import MagicMock

import pytest

from basilisk.audio.streams import AudioInputStream, AudioOutputStream
from basilisk.provider_engine.voice_session import (
	BaseVoiceSession,
	GeminiLiveVoiceSession,
	OpenAIRealtimeVoiceSession,
	VoiceSessionCallbacks,
	VoiceSessionConfig,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**kwargs) -> VoiceSessionConfig:
	"""Return a minimal VoiceSessionConfig."""
	defaults = dict(model="gpt-realtime", voice="marin")
	defaults.update(kwargs)
	return VoiceSessionConfig(**defaults)


def _make_callbacks(**kwargs) -> VoiceSessionCallbacks:
	"""Return a VoiceSessionCallbacks with optional overrides."""
	return VoiceSessionCallbacks(**kwargs)


def _make_session(**kwargs) -> OpenAIRealtimeVoiceSession:
	"""Return an OpenAIRealtimeVoiceSession with a mock account."""
	account = MagicMock()
	account.api_key.get_secret_value.return_value = "sk-test"
	account.active_organization_key = None
	account.custom_base_url = None
	account.provider.base_url = "https://api.openai.com"
	cfg = kwargs.pop("config", _make_config())
	cbs = kwargs.pop("callbacks", _make_callbacks())
	return OpenAIRealtimeVoiceSession(
		account=account, config=cfg, callbacks=cbs
	)


def _make_event(type_: str, **attrs):
	"""Return a mock event object."""
	event = MagicMock()
	event.type = type_
	for k, v in attrs.items():
		setattr(event, k, v)
	return event


# ---------------------------------------------------------------------------
# VoiceSessionConfig
# ---------------------------------------------------------------------------


class TestVoiceSessionConfig:
	"""Tests for VoiceSessionConfig dataclass."""

	def test_required_fields(self):
		"""Model and voice are required."""
		cfg = VoiceSessionConfig(model="gpt-realtime", voice="marin")
		assert cfg.model == "gpt-realtime"
		assert cfg.voice == "marin"

	def test_defaults(self):
		"""Default values are applied correctly."""
		cfg = _make_config()
		assert cfg.vad_type == "semantic_vad"
		assert cfg.vad_eagerness == "auto"
		assert cfg.create_response is True
		assert cfg.interrupt_response is True
		assert cfg.input_sample_rate == 24000
		assert cfg.output_sample_rate == 24000
		assert cfg.output_speed is None
		assert cfg.instructions is None
		assert cfg.transcription_model is None

	def test_custom_values(self):
		"""Custom values are stored."""
		cfg = _make_config(
			instructions="Be concise",
			transcription_model="whisper-1",
			transcription_language="fr",
			transcription_prompt="basilisk",
			vad_type="server_vad",
			vad_eagerness="high",
			output_speed=1.2,
		)
		assert cfg.instructions == "Be concise"
		assert cfg.transcription_model == "whisper-1"
		assert cfg.transcription_language == "fr"
		assert cfg.transcription_prompt == "basilisk"
		assert cfg.vad_type == "server_vad"
		assert cfg.vad_eagerness == "high"
		assert cfg.output_speed == 1.2


# ---------------------------------------------------------------------------
# VoiceSessionCallbacks
# ---------------------------------------------------------------------------


class TestVoiceSessionCallbacks:
	"""Tests for VoiceSessionCallbacks dataclass."""

	def test_all_none_by_default(self):
		"""All callbacks default to None."""
		cbs = VoiceSessionCallbacks()
		assert cbs.on_status is None
		assert cbs.on_user_text is None
		assert cbs.on_assistant_text is None
		assert cbs.on_audio_chunk is None
		assert cbs.on_error is None

	def test_callbacks_stored(self):
		"""Provided callables are stored."""
		fn = MagicMock()
		cbs = VoiceSessionCallbacks(on_status=fn)
		assert cbs.on_status is fn


# ---------------------------------------------------------------------------
# BaseVoiceSession
# ---------------------------------------------------------------------------


class TestBaseVoiceSession:
	"""Tests for BaseVoiceSession abstract class."""

	def test_stores_config_and_callbacks(self):
		"""Constructor stores config and callbacks."""
		cfg = _make_config()
		cbs = _make_callbacks()
		session = BaseVoiceSession(config=cfg, callbacks=cbs)
		assert session.config is cfg
		assert session.callbacks is cbs

	def test_start_raises(self):
		"""start() raises NotImplementedError."""
		session = BaseVoiceSession(
			config=_make_config(), callbacks=_make_callbacks()
		)
		with pytest.raises(NotImplementedError):
			asyncio.run(session.start())

	def test_stop_raises(self):
		"""stop() raises NotImplementedError."""
		session = BaseVoiceSession(
			config=_make_config(), callbacks=_make_callbacks()
		)
		with pytest.raises(NotImplementedError):
			asyncio.run(session.stop())


# ---------------------------------------------------------------------------
# AudioOutputStream (formerly PCM16OutputPlayer)
# ---------------------------------------------------------------------------


class TestAudioOutputStream:
	"""Tests for AudioOutputStream buffer logic (no audio hardware)."""

	def test_initial_state(self):
		"""Buffer is empty on construction."""
		player = AudioOutputStream(sample_rate=24000)
		assert len(player._buffer) == 0
		assert player._stream is None

	def test_enqueue_adds_to_buffer(self):
		"""enqueue() appends bytes to the buffer."""
		player = AudioOutputStream(sample_rate=24000)
		player.enqueue(b"\x01\x02\x03\x04")
		assert player._buffer == bytearray(b"\x01\x02\x03\x04")

	def test_enqueue_empty_data_ignored(self):
		"""enqueue() with empty bytes does nothing."""
		player = AudioOutputStream(sample_rate=24000)
		player.enqueue(b"")
		assert len(player._buffer) == 0

	def test_enqueue_accumulates(self):
		"""Multiple enqueue() calls accumulate data."""
		player = AudioOutputStream(sample_rate=24000)
		player.enqueue(b"\x01\x02")
		player.enqueue(b"\x03\x04")
		assert player._buffer == bytearray(b"\x01\x02\x03\x04")

	def test_clear_empties_buffer(self):
		"""clear() resets the buffer."""
		player = AudioOutputStream(sample_rate=24000)
		player.enqueue(b"\x01\x02\x03\x04")
		player.clear()
		assert len(player._buffer) == 0

	def test_callback_full_buffer(self):
		"""_callback() drains exactly the requested bytes from the buffer."""
		player = AudioOutputStream(sample_rate=24000, channels=1)
		# 4 frames × 1 channel × 2 bytes = 8 bytes
		player.enqueue(b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a")
		outdata = bytearray(8)
		player._callback(outdata, 4, None, None)
		assert bytes(outdata) == b"\x01\x02\x03\x04\x05\x06\x07\x08"
		# Remaining bytes stay in buffer
		assert player._buffer == bytearray(b"\x09\x0a")

	def test_callback_partial_buffer_pads_zeros(self):
		"""_callback() pads with zeros when buffer has fewer bytes than needed."""
		player = AudioOutputStream(sample_rate=24000, channels=1)
		player.enqueue(b"\x01\x02")
		outdata = bytearray(8)
		player._callback(outdata, 4, None, None)
		assert bytes(outdata) == b"\x01\x02\x00\x00\x00\x00\x00\x00"
		assert len(player._buffer) == 0

	def test_callback_empty_buffer_all_zeros(self):
		"""_callback() fills with zeros when buffer is empty."""
		player = AudioOutputStream(sample_rate=24000, channels=1)
		outdata = bytearray(8)
		player._callback(outdata, 4, None, None)
		assert bytes(outdata) == b"\x00" * 8

	def test_stop_when_no_stream(self):
		"""stop() is a no-op when no stream is active."""
		player = AudioOutputStream(sample_rate=24000)
		player.stop()  # Should not raise
		assert player._stream is None


# ---------------------------------------------------------------------------
# AudioInputStream
# ---------------------------------------------------------------------------


class TestAudioInputStream:
	"""Tests for AudioInputStream (construction only — no hardware)."""

	def test_initial_state(self):
		"""Stream is None and callback is stored on construction."""
		cb = MagicMock()
		stream = AudioInputStream(sample_rate=24000, channels=1, on_audio=cb)
		assert stream._stream is None
		assert stream._on_audio is cb
		assert stream.sample_rate == 24000
		assert stream.channels == 1
		assert stream._device is None

	def test_stop_when_no_stream(self):
		"""stop() is a no-op when no stream is open."""
		stream = AudioInputStream(
			sample_rate=24000, channels=1, on_audio=MagicMock()
		)
		stream.stop()  # Should not raise


# ---------------------------------------------------------------------------
# OpenAIRealtimeVoiceSession — pure logic methods
# ---------------------------------------------------------------------------


class TestOpenAISessionInit:
	"""Tests for OpenAIRealtimeVoiceSession initialisation."""

	def test_initial_state(self):
		"""All internal fields start as None / empty."""
		session = _make_session()
		assert session._client is None
		assert session._connection is None
		assert session._stop_event is not None
		assert not session._stop_event.is_set()
		assert session._user_transcript_buffer == ""


class TestBuildSessionPayload:
	"""Tests for OpenAIRealtimeVoiceSession._build_session_payload."""

	def test_minimal_config(self):
		"""Payload has correct structure with minimal config."""
		cfg = _make_config(vad_type="semantic_vad")
		session = _make_session(config=cfg)
		payload = session._build_session_payload()

		assert payload["type"] == "realtime"
		assert payload["model"] == "gpt-realtime"
		assert payload["output_modalities"] == ["audio"]
		assert payload["audio"]["output"]["voice"] == "marin"
		assert "transcription" not in payload["audio"]["input"]
		assert (
			payload["audio"]["input"]["turn_detection"]["type"]
			== "semantic_vad"
		)
		assert "eagerness" in payload["audio"]["input"]["turn_detection"]

	def test_instructions_set(self):
		"""Instructions in config appear in the payload."""
		cfg = _make_config(instructions="Be concise")
		session = _make_session(config=cfg)
		payload = session._build_session_payload()
		assert payload["instructions"] == "Be concise"

	def test_instructions_empty_string_when_none(self):
		"""None instructions becomes empty string in the payload."""
		cfg = _make_config(instructions=None)
		session = _make_session(config=cfg)
		payload = session._build_session_payload()
		assert payload["instructions"] == ""

	def test_transcription_model_included(self):
		"""Transcription block added when transcription_model is set."""
		cfg = _make_config(transcription_model="gpt-4o-mini-transcribe")
		session = _make_session(config=cfg)
		payload = session._build_session_payload()
		transcription = payload["audio"]["input"]["transcription"]
		assert transcription["model"] == "gpt-4o-mini-transcribe"
		assert "language" not in transcription
		assert "prompt" not in transcription

	def test_transcription_language_and_prompt(self):
		"""Language and prompt are added inside the transcription block."""
		cfg = _make_config(
			transcription_model="gpt-4o-mini-transcribe",
			transcription_language="fr",
			transcription_prompt="basilisk",
		)
		session = _make_session(config=cfg)
		payload = session._build_session_payload()
		transcription = payload["audio"]["input"]["transcription"]
		assert transcription["language"] == "fr"
		assert transcription["prompt"] == "basilisk"

	def test_non_semantic_vad_no_eagerness(self):
		"""server_vad type does not include eagerness."""
		cfg = _make_config(vad_type="server_vad")
		session = _make_session(config=cfg)
		payload = session._build_session_payload()
		turn = payload["audio"]["input"]["turn_detection"]
		assert "eagerness" not in turn

	def test_output_speed_included(self):
		"""output_speed is added to audio output when set."""
		cfg = _make_config(output_speed=1.2)
		session = _make_session(config=cfg)
		payload = session._build_session_payload()
		assert payload["audio"]["output"]["speed"] == 1.2

	def test_output_speed_absent_when_none(self):
		"""output_speed key is absent when not configured."""
		cfg = _make_config(output_speed=None)
		session = _make_session(config=cfg)
		payload = session._build_session_payload()
		assert "speed" not in payload["audio"]["output"]


class TestEnqueueAudio:
	"""Tests for OpenAIRealtimeVoiceSession._enqueue_audio."""

	def test_returns_early_when_stop_event_set(self):
		"""No call_soon_threadsafe when stop event is set."""
		session = _make_session()
		session._stop_event.set()
		session._loop = MagicMock()
		session._enqueue_audio(b"\x01\x02")
		session._loop.call_soon_threadsafe.assert_not_called()

	def test_returns_early_when_no_loop(self):
		"""No call_soon_threadsafe when loop is None."""
		session = _make_session()
		session._loop = None
		session._audio_queue = MagicMock()
		session._enqueue_audio(b"\x01\x02")

	def test_returns_early_when_loop_closed(self):
		"""No call_soon_threadsafe when loop is closed."""
		session = _make_session()
		loop = MagicMock()
		loop.is_closed.return_value = True
		session._loop = loop
		session._enqueue_audio(b"\x01\x02")
		loop.call_soon_threadsafe.assert_not_called()

	def test_schedules_queue_put_when_active(self):
		"""call_soon_threadsafe is called when loop is open and event not set."""
		session = _make_session()
		loop = MagicMock()
		loop.is_closed.return_value = False
		session._loop = loop
		session._audio_queue = MagicMock()
		session._enqueue_audio(b"\x01\x02")
		loop.call_soon_threadsafe.assert_called_once_with(
			session._safe_queue_put, b"\x01\x02"
		)


class TestSafeQueuePut:
	"""Tests for OpenAIRealtimeVoiceSession._safe_queue_put."""

	def test_puts_data_in_queue(self):
		"""Data is added to the queue when not full."""
		session = _make_session()
		session._audio_queue = asyncio.Queue()
		session._safe_queue_put(b"\x01")
		assert session._audio_queue.qsize() == 1

	def test_ignores_full_queue(self):
		"""QueueFull is silently swallowed."""
		session = _make_session()
		q = asyncio.Queue(maxsize=1)
		q.put_nowait(b"\xff")
		session._audio_queue = q
		session._safe_queue_put(b"\x01")  # Should not raise


# ---------------------------------------------------------------------------
# Event dispatch methods
# ---------------------------------------------------------------------------


class TestDispatchEvent:
	"""Tests for _dispatch_event routing."""

	def test_input_audio_routes_to_handle_input(self):
		"""input_audio_buffer.* events route to _handle_input_event."""
		session = _make_session()
		session._handle_input_event = MagicMock()
		event = _make_event("input_audio_buffer.speech_started")
		session._dispatch_event(event)
		session._handle_input_event.assert_called_once_with(event)

	def test_conversation_item_routes_to_handle_input(self):
		"""conversation.item.* events route to _handle_input_event."""
		session = _make_session()
		session._handle_input_event = MagicMock()
		event = _make_event("conversation.item.input_audio_transcription.delta")
		session._dispatch_event(event)
		session._handle_input_event.assert_called_once_with(event)

	def test_response_routes_to_handle_response(self):
		"""response.* events route to _handle_response_event."""
		session = _make_session()
		session._handle_response_event = MagicMock()
		event = _make_event("response.done")
		session._dispatch_event(event)
		session._handle_response_event.assert_called_once_with(event)

	def test_error_calls_on_error(self):
		"""Error event invokes the on_error callback."""
		on_error = MagicMock()
		cbs = _make_callbacks(on_error=on_error)
		session = _make_session(callbacks=cbs)
		event = _make_event("error")
		event.error.message = "oops"
		session._dispatch_event(event)
		on_error.assert_called_once_with("oops")

	def test_error_without_callback(self):
		"""Error event with no callback does not raise."""
		session = _make_session(callbacks=_make_callbacks())
		event = _make_event("error")
		event.error.message = "oops"
		session._dispatch_event(event)

	def test_unknown_event_ignored(self):
		"""Unknown event types do not raise and make no callbacks."""
		on_status = MagicMock()
		session = _make_session(callbacks=_make_callbacks(on_status=on_status))
		event = _make_event("some.unknown.event")
		session._dispatch_event(event)
		on_status.assert_not_called()


class TestHandleInputEvent:
	"""Tests for _handle_input_event."""

	def test_speech_started_clears_player_and_calls_status(self):
		"""speech_started clears the output player and fires on_status."""
		on_status = MagicMock()
		cbs = _make_callbacks(on_status=on_status)
		session = _make_session(callbacks=cbs)
		player = MagicMock()
		session._output_stream = player
		event = _make_event("input_audio_buffer.speech_started")
		session._handle_input_event(event)
		player.clear.assert_called_once()
		on_status.assert_called_once()

	def test_speech_started_no_player(self):
		"""speech_started without output player still fires on_status."""
		on_status = MagicMock()
		session = _make_session(callbacks=_make_callbacks(on_status=on_status))
		session._output_stream = None
		session._handle_input_event(
			_make_event("input_audio_buffer.speech_started")
		)
		on_status.assert_called_once()

	def test_speech_stopped_calls_status(self):
		"""speech_stopped fires on_status."""
		on_status = MagicMock()
		session = _make_session(callbacks=_make_callbacks(on_status=on_status))
		session._handle_input_event(
			_make_event("input_audio_buffer.speech_stopped")
		)
		on_status.assert_called_once()

	def test_transcription_delta_accumulates(self):
		"""Transcription delta events append to the buffer."""
		session = _make_session()
		event = _make_event(
			"conversation.item.input_audio_transcription.delta", delta="hello "
		)
		session._handle_input_event(event)
		assert session._user_transcript_buffer == "hello "
		event2 = _make_event(
			"conversation.item.input_audio_transcription.delta", delta="world"
		)
		session._handle_input_event(event2)
		assert session._user_transcript_buffer == "hello world"

	def test_transcription_completed_uses_event_transcript(self):
		"""Completed event uses event.transcript when available."""
		on_user_text = MagicMock()
		cbs = _make_callbacks(on_user_text=on_user_text)
		session = _make_session(callbacks=cbs)
		session._user_transcript_buffer = "fallback"
		event = _make_event(
			"conversation.item.input_audio_transcription.completed",
			transcript="final text",
		)
		session._handle_input_event(event)
		on_user_text.assert_called_once_with("final text", True)
		assert session._user_transcript_buffer == ""

	def test_transcription_completed_falls_back_to_buffer(self):
		"""Completed event falls back to buffer when transcript is falsy."""
		on_user_text = MagicMock()
		session = _make_session(
			callbacks=_make_callbacks(on_user_text=on_user_text)
		)
		session._user_transcript_buffer = "buffered text"
		event = _make_event(
			"conversation.item.input_audio_transcription.completed",
			transcript="",
		)
		session._handle_input_event(event)
		on_user_text.assert_called_once_with("buffered text", True)


class TestHandleResponseEvent:
	"""Tests for _handle_response_event."""

	def test_response_done_calls_status(self):
		"""response.done fires on_status."""
		on_status = MagicMock()
		session = _make_session(callbacks=_make_callbacks(on_status=on_status))
		session._handle_response_event(_make_event("response.done"))
		on_status.assert_called_once()

	def test_audio_delta_enqueues_and_calls_chunk(self):
		"""response.output_audio.delta enqueues decoded bytes and fires on_audio_chunk."""
		on_audio_chunk = MagicMock()
		cbs = _make_callbacks(on_audio_chunk=on_audio_chunk)
		session = _make_session(callbacks=cbs)
		player = MagicMock()
		session._output_stream = player
		raw = b"\x01\x02\x03\x04"
		encoded = base64.b64encode(raw).decode("ascii")
		event = _make_event("response.output_audio.delta", delta=encoded)
		session._handle_response_event(event)
		player.enqueue.assert_called_once_with(raw)
		on_audio_chunk.assert_called_once_with(
			raw, session.config.output_sample_rate
		)

	def test_audio_delta_no_player(self):
		"""response.output_audio.delta with no player still fires on_audio_chunk."""
		on_audio_chunk = MagicMock()
		session = _make_session(
			callbacks=_make_callbacks(on_audio_chunk=on_audio_chunk)
		)
		session._output_stream = None
		raw = b"\x01\x02"
		event = _make_event(
			"response.output_audio.delta", delta=base64.b64encode(raw).decode()
		)
		session._handle_response_event(event)
		on_audio_chunk.assert_called_once_with(
			raw, session.config.output_sample_rate
		)

	def test_text_events_routed_to_handle_response_text(self):
		"""Text event types are forwarded to _handle_response_text_event."""
		session = _make_session()
		session._handle_response_text_event = MagicMock()
		for etype in (
			"response.output_audio_transcript.delta",
			"response.output_audio_transcript.done",
			"response.output_text.delta",
			"response.output_text.done",
		):
			session._handle_response_text_event.reset_mock()
			session._handle_response_event(_make_event(etype))
			session._handle_response_text_event.assert_called_once()


class TestHandleResponseTextEvent:
	"""Tests for _handle_response_text_event."""

	@pytest.mark.parametrize(
		("event_type", "attr", "is_final"),
		[
			("response.output_audio_transcript.delta", "delta", False),
			("response.output_audio_transcript.done", "transcript", True),
			("response.output_text.delta", "delta", False),
			("response.output_text.done", "text", True),
		],
	)
	def test_fires_on_assistant_text(self, event_type, attr, is_final):
		"""Each text event type fires on_assistant_text with correct finality."""
		on_assistant_text = MagicMock()
		session = _make_session(
			callbacks=_make_callbacks(on_assistant_text=on_assistant_text)
		)
		event = _make_event(event_type, **{attr: "hello"})
		session._handle_response_text_event(event)
		on_assistant_text.assert_called_once_with("hello", is_final)

	def test_no_callback_no_raise(self):
		"""Text event with no on_assistant_text callback does not raise."""
		session = _make_session(callbacks=_make_callbacks())
		event = _make_event("response.output_text.delta", delta="hi")
		session._handle_response_text_event(event)


# ---------------------------------------------------------------------------
# GeminiLiveVoiceSession
# ---------------------------------------------------------------------------


class TestGeminiLiveVoiceSession:
	"""Tests for GeminiLiveVoiceSession placeholder."""

	def test_start_calls_on_error(self):
		"""start() fires on_error with 'not implemented' message."""
		on_error = MagicMock()
		session = GeminiLiveVoiceSession(
			config=_make_config(), callbacks=_make_callbacks(on_error=on_error)
		)
		asyncio.run(session.start())
		on_error.assert_called_once()
		assert "not implemented" in on_error.call_args[0][0].lower()

	def test_start_without_error_callback(self):
		"""start() without on_error callback does not raise."""
		session = GeminiLiveVoiceSession(
			config=_make_config(), callbacks=_make_callbacks()
		)
		asyncio.run(session.start())

	def test_stop_is_noop(self):
		"""stop() completes without error."""
		session = GeminiLiveVoiceSession(
			config=_make_config(), callbacks=_make_callbacks()
		)
		asyncio.run(session.stop())
