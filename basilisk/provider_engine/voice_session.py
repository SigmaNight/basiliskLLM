"""Voice session abstractions and provider-specific implementations."""

from __future__ import annotations

import asyncio
import base64
import logging
import threading
from dataclasses import dataclass
from typing import Callable, Optional

import sounddevice as sd
from openai import AsyncOpenAI

log = logging.getLogger(__name__)


@dataclass
class VoiceSessionConfig:
	"""Configuration for a realtime voice session."""

	model: str
	voice: str
	instructions: Optional[str] = None
	transcription_model: Optional[str] = None
	transcription_language: Optional[str] = None
	transcription_prompt: Optional[str] = None
	vad_type: str = "semantic_vad"
	vad_eagerness: str = "auto"
	create_response: bool = True
	interrupt_response: bool = True
	input_sample_rate: int = 24000
	input_channels: int = 1
	output_sample_rate: int = 24000
	output_channels: int = 1
	output_speed: Optional[float] = None


@dataclass
class VoiceSessionCallbacks:
	"""Callbacks for realtime voice sessions."""

	on_status: Optional[Callable[[str], None]] = None
	on_user_text: Optional[Callable[[str, bool], None]] = None
	on_assistant_text: Optional[Callable[[str, bool], None]] = None
	on_audio_chunk: Optional[Callable[[bytes, int], None]] = None
	on_error: Optional[Callable[[str], None]] = None


class BaseVoiceSession:
	"""Abstract voice session."""

	def __init__(
		self, config: VoiceSessionConfig, callbacks: VoiceSessionCallbacks
	):
		"""Initialize the voice session with config and callbacks."""
		self.config = config
		self.callbacks = callbacks

	async def start(self) -> None:
		"""Start the voice session."""
		raise NotImplementedError

	async def stop(self) -> None:
		"""Stop the voice session."""
		raise NotImplementedError


class PCM16OutputPlayer:
	"""Simple PCM16 audio output buffer."""

	def __init__(self, sample_rate: int, channels: int = 1) -> None:
		"""Initialize the output player with sample rate and channel count."""
		self.sample_rate = sample_rate
		self.channels = channels
		self._buffer = bytearray()
		self._lock = threading.Lock()
		self._stream: Optional[sd.RawOutputStream] = None

	def start(self) -> None:
		"""Start the audio output stream."""
		if self._stream:
			return
		self._stream = sd.RawOutputStream(
			samplerate=self.sample_rate,
			channels=self.channels,
			dtype="int16",
			callback=self._callback,
		)
		self._stream.start()

	def stop(self) -> None:
		"""Stop and close the audio output stream."""
		if not self._stream:
			return
		self._stream.stop()
		self._stream.close()
		self._stream = None
		self.clear()

	def clear(self) -> None:
		"""Clear the audio buffer."""
		with self._lock:
			self._buffer = bytearray()

	def enqueue(self, data: bytes) -> None:
		"""Append PCM16 bytes to the playback buffer."""
		if not data:
			return
		with self._lock:
			self._buffer.extend(data)

	def _callback(self, outdata, frames, time_info, status) -> None:
		bytes_needed = frames * self.channels * 2
		with self._lock:
			if len(self._buffer) >= bytes_needed:
				chunk = self._buffer[:bytes_needed]
				del self._buffer[:bytes_needed]
			else:
				chunk = bytes(self._buffer)
				self._buffer = bytearray()
		if len(chunk) < bytes_needed:
			chunk = chunk + b"\x00" * (bytes_needed - len(chunk))
		outdata[:] = chunk


class AudioInputStream:
	"""Captures PCM16 audio and forwards bytes via a callback."""

	def __init__(
		self, sample_rate: int, channels: int, on_audio: Callable[[bytes], None]
	) -> None:
		"""Initialize the input stream with sample rate, channels, and callback."""
		self.sample_rate = sample_rate
		self.channels = channels
		self._on_audio = on_audio
		self._stream: Optional[sd.InputStream] = None

	def start(self) -> None:
		"""Start capturing audio from the default input device."""
		if self._stream:
			return
		self._stream = sd.InputStream(
			samplerate=self.sample_rate,
			channels=self.channels,
			dtype="int16",
			callback=self._callback,
		)
		self._stream.start()

	def stop(self) -> None:
		"""Stop and close the audio input stream."""
		if not self._stream:
			return
		self._stream.stop()
		self._stream.close()
		self._stream = None

	def _callback(self, indata, frames, time_info, status) -> None:
		self._on_audio(indata.tobytes())


class OpenAIRealtimeVoiceSession(BaseVoiceSession):
	"""OpenAI realtime voice session using the official SDK."""

	def __init__(
		self,
		account,
		config: VoiceSessionConfig,
		callbacks: VoiceSessionCallbacks,
	) -> None:
		"""Initialize with account credentials, config, and event callbacks."""
		super().__init__(config, callbacks)
		self._account = account
		self._client: Optional[AsyncOpenAI] = None
		self._connection = None
		self._stop_event = asyncio.Event()
		self._audio_queue: Optional[asyncio.Queue] = None
		self._input_stream: Optional[AudioInputStream] = None
		self._output_player: Optional[PCM16OutputPlayer] = None
		self._loop: Optional[asyncio.AbstractEventLoop] = None
		self._user_transcript_buffer: str = ""

	async def start(self) -> None:
		"""Connect to the OpenAI Realtime API and stream audio bidirectionally."""
		self._loop = asyncio.get_running_loop()
		if self.config.input_sample_rate != 24000:
			log.warning("Forcing input sample rate to 24000 Hz for OpenAI")
			self.config.input_sample_rate = 24000
		if self.config.output_sample_rate != 24000:
			log.warning("Forcing output sample rate to 24000 Hz for OpenAI")
			self.config.output_sample_rate = 24000
		self._audio_queue = asyncio.Queue(maxsize=8)
		self._client = AsyncOpenAI(
			api_key=self._account.api_key.get_secret_value(),
			organization=(
				self._account.active_organization_key.get_secret_value()
				if self._account.active_organization_key
				else None
			),
			base_url=self._account.custom_base_url
			or str(self._account.provider.base_url),
		)
		try:
			self._connection = await self._client.realtime.connect(
				model=self.config.model
			).enter()
			await self._connection.session.update(
				session=self._build_session_payload()
			)
		except Exception as exc:
			log.error("Failed to start realtime session: %s", exc)
			if self.callbacks.on_error:
				self.callbacks.on_error(str(exc))
			self._stop_event.set()
			return

		self._output_player = PCM16OutputPlayer(
			sample_rate=self.config.output_sample_rate,
			channels=self.config.output_channels,
		)
		try:
			self._output_player.start()
		except Exception as exc:
			log.error("Failed to start audio output: %s", exc)
			if self.callbacks.on_error:
				self.callbacks.on_error(str(exc))
			self._stop_event.set()
			return

		self._input_stream = AudioInputStream(
			sample_rate=self.config.input_sample_rate,
			channels=self.config.input_channels,
			on_audio=self._enqueue_audio,
		)
		try:
			self._input_stream.start()
		except Exception as exc:
			log.error("Failed to start audio input: %s", exc)
			if self.callbacks.on_error:
				self.callbacks.on_error(str(exc))
			self._stop_event.set()
			return

		send_task = asyncio.create_task(self._send_audio_loop())
		recv_task = asyncio.create_task(self._recv_loop())

		if self.callbacks.on_status:
			self.callbacks.on_status(_("Listening"))

		await self._stop_event.wait()

		send_task.cancel()
		recv_task.cancel()
		await asyncio.gather(send_task, recv_task, return_exceptions=True)
		await self._cleanup()

	async def stop(self) -> None:
		"""Signal the session to stop gracefully."""
		if self._stop_event.is_set():
			return
		if self._input_stream:
			self._input_stream.stop()
			self._input_stream = None
		self._stop_event.set()

	async def _cleanup(self) -> None:
		if self._input_stream:
			self._input_stream.stop()
			self._input_stream = None
		if self._output_player:
			self._output_player.stop()
			self._output_player = None
		if self._connection is not None:
			try:
				await self._connection.response.cancel()
			except Exception:
				log.debug("Failed to cancel response", exc_info=True)
			try:
				await self._connection.close()
			except Exception:
				log.debug("Failed to close realtime connection", exc_info=True)
			self._connection = None

	def _build_session_payload(self) -> dict:
		audio_input = {"format": {"type": "audio/pcm", "rate": 24000}}
		if self.config.transcription_model:
			transcription = {"model": self.config.transcription_model}
			if self.config.transcription_language:
				transcription["language"] = self.config.transcription_language
			if self.config.transcription_prompt:
				transcription["prompt"] = self.config.transcription_prompt
			audio_input["transcription"] = transcription
		turn_detection = {
			"type": self.config.vad_type,
			"create_response": self.config.create_response,
			"interrupt_response": self.config.interrupt_response,
		}
		if self.config.vad_type == "semantic_vad":
			turn_detection["eagerness"] = self.config.vad_eagerness
		audio_input["turn_detection"] = turn_detection
		audio_output = {
			"format": {"type": "audio/pcm", "rate": 24000},
			"voice": self.config.voice,
		}
		if self.config.output_speed:
			audio_output["speed"] = self.config.output_speed
		return {
			"type": "realtime",
			"model": self.config.model,
			"output_modalities": ["audio"],
			"instructions": self.config.instructions or "",
			"audio": {"input": audio_input, "output": audio_output},
		}

	def _enqueue_audio(self, data: bytes) -> None:
		if (
			self._stop_event.is_set()
			or not self._loop
			or self._loop.is_closed()
			or not self._audio_queue
		):
			return
		self._loop.call_soon_threadsafe(self._safe_queue_put, data)

	def _safe_queue_put(self, data: bytes) -> None:
		try:
			self._audio_queue.put_nowait(data)
		except asyncio.QueueFull:
			return

	async def _send_audio_loop(self) -> None:
		assert self._audio_queue is not None
		while not self._stop_event.is_set():
			data = await self._audio_queue.get()
			if self._stop_event.is_set():
				break
			if not data:
				continue
			try:
				await self._connection.input_audio_buffer.append(
					audio=base64.b64encode(data).decode("ascii")
				)
			except Exception as exc:
				log.error("Failed to append audio: %s", exc)

	async def _recv_loop(self) -> None:
		"""Receive and dispatch events from the OpenAI Realtime connection."""
		try:
			async for event in self._connection:
				self._dispatch_event(event)
		except Exception as exc:
			log.error("Realtime receive loop failed: %s", exc)
			if self.callbacks.on_error:
				self.callbacks.on_error(str(exc))
		finally:
			self._stop_event.set()

	def _dispatch_event(self, event) -> None:
		"""Dispatch a single realtime event to the appropriate callback."""
		etype = event.type
		if etype.startswith("input_audio_buffer.") or etype.startswith(
			"conversation.item."
		):
			self._handle_input_event(event)
		elif etype.startswith("response."):
			self._handle_response_event(event)
		elif etype == "error":
			if self.callbacks.on_error:
				self.callbacks.on_error(event.error.message)

	def _handle_input_event(self, event) -> None:
		"""Handle input audio buffer and transcription events."""
		match event.type:
			case "input_audio_buffer.speech_started":
				if self._output_player:
					self._output_player.clear()
				if self.callbacks.on_status:
					self.callbacks.on_status(_("Listening"))
			case "input_audio_buffer.speech_stopped":
				if self.callbacks.on_status:
					self.callbacks.on_status(_("Transcribing..."))
			case "conversation.item.input_audio_transcription.delta":
				self._user_transcript_buffer += event.delta
			case "conversation.item.input_audio_transcription.completed":
				transcript = event.transcript or self._user_transcript_buffer
				self._user_transcript_buffer = ""
				if self.callbacks.on_user_text:
					self.callbacks.on_user_text(transcript, True)

	def _handle_response_event(self, event) -> None:
		"""Handle response output events (text, audio, status)."""
		etype = event.type
		if etype in (
			"response.output_audio_transcript.delta",
			"response.output_audio_transcript.done",
			"response.output_text.delta",
			"response.output_text.done",
		):
			self._handle_response_text_event(event)
		elif etype == "response.output_audio.delta":
			audio_bytes = base64.b64decode(event.delta)
			if self._output_player:
				self._output_player.enqueue(audio_bytes)
			if self.callbacks.on_audio_chunk:
				self.callbacks.on_audio_chunk(
					audio_bytes, self.config.output_sample_rate
				)
		elif etype == "response.done":
			if self.callbacks.on_status:
				self.callbacks.on_status(_("Ready"))

	def _handle_response_text_event(self, event) -> None:
		"""Handle assistant transcript and text delta/done events."""
		match event.type:
			case "response.output_audio_transcript.delta":
				if self.callbacks.on_assistant_text:
					self.callbacks.on_assistant_text(event.delta, False)
			case "response.output_audio_transcript.done":
				if self.callbacks.on_assistant_text:
					self.callbacks.on_assistant_text(event.transcript, True)
			case "response.output_text.delta":
				if self.callbacks.on_assistant_text:
					self.callbacks.on_assistant_text(event.delta, False)
			case "response.output_text.done":
				if self.callbacks.on_assistant_text:
					self.callbacks.on_assistant_text(event.text, True)


class GeminiLiveVoiceSession(BaseVoiceSession):
	"""Placeholder for Gemini Live API."""

	async def start(self) -> None:
		"""Signal that Gemini Live is not yet implemented."""
		if self.callbacks.on_error:
			self.callbacks.on_error("Gemini Live voice session not implemented")

	async def stop(self) -> None:
		"""No-op stop for the Gemini Live placeholder."""
		return
