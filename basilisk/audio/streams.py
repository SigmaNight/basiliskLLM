"""Audio stream abstractions for BasiliskLLM.

Provides _BaseAudioStream, AudioInputStream, AudioOutputStream, and
AudioRecorder.  All sounddevice usage is isolated to this module.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import wave
from typing import Callable, Optional

import sounddevice as sd

log = logging.getLogger(__name__)


class _BaseAudioStream:
	"""Common lifecycle (start/stop) for all audio streams."""

	def __init__(self) -> None:
		"""Initialise with no active stream."""
		self._stream = None

	def start(self) -> None:
		"""Create and start the stream."""
		if self._stream is not None:
			return
		self._stream = self._create_stream()
		self._stream.start()

	def stop(self) -> None:
		"""Stop and close the stream."""
		if self._stream is None:
			return
		try:
			self._stream.stop()
			self._stream.close()
		except Exception:
			log.debug("Error stopping stream", exc_info=True)
		finally:
			self._stream = None

	def _create_stream(self):
		"""Create the sounddevice stream — override in subclasses."""
		raise NotImplementedError


class AudioInputStream(_BaseAudioStream):
	"""Captures PCM16 audio from the microphone and forwards bytes via callback."""

	def __init__(
		self,
		sample_rate: int,
		channels: int,
		on_audio: Callable[[bytes], None],
		device: Optional[int] = None,
	) -> None:
		"""Initialise the input stream.

		Args:
			sample_rate: Sample rate in Hz.
			channels: Number of input channels.
			on_audio: Callback receiving raw PCM16 bytes per callback.
			device: sounddevice device index, or None for the system default.
		"""
		super().__init__()
		self.sample_rate = sample_rate
		self.channels = channels
		self._on_audio = on_audio
		self._device = device

	def _create_stream(self) -> sd.InputStream:
		"""Create the sounddevice InputStream."""
		return sd.InputStream(
			samplerate=self.sample_rate,
			channels=self.channels,
			dtype="int16",
			device=self._device,
			callback=self._callback,
		)

	def _callback(self, indata, frames, time_info, status) -> None:
		if status:
			log.warning("Input stream status: %s", status)
		self._on_audio(indata.tobytes())


class AudioOutputStream(_BaseAudioStream):
	"""PCM16 output for real-time streaming and WAV notification playback.

	Supports two modes:
	- one-shot: enqueue(data) → played once, silence afterwards.
	- loop: set_loop(data) → replayed continuously until clear_loop().

	Loop mode takes priority over the one-shot buffer.
	"""

	def __init__(
		self, sample_rate: int, channels: int = 1, device: Optional[int] = None
	) -> None:
		"""Initialise the output stream.

		Args:
			sample_rate: Sample rate in Hz.
			channels: Number of output channels.
			device: sounddevice device index, or None for the system default.
		"""
		super().__init__()
		self.sample_rate = sample_rate
		self.channels = channels
		self._device = device
		self._buffer = bytearray()
		self._lock = threading.Lock()
		self._loop_data: Optional[bytes] = None
		self._loop_pos: int = 0

	def _create_stream(self) -> sd.RawOutputStream:
		"""Create the sounddevice RawOutputStream (int16)."""
		return sd.RawOutputStream(
			samplerate=self.sample_rate,
			channels=self.channels,
			dtype="int16",
			device=self._device,
			callback=self._callback,
		)

	def enqueue(self, data: bytes) -> None:
		"""Append PCM16 bytes to the one-shot playback buffer (thread-safe).

		Args:
			data: PCM16 (int16) bytes to append.
		"""
		if not data:
			return
		with self._lock:
			self._buffer.extend(data)

	def clear(self) -> None:
		"""Clear the one-shot buffer."""
		with self._lock:
			self._buffer = bytearray()

	def set_loop(self, data: bytes) -> None:
		"""Enable loop mode with the given PCM16 data.

		Args:
			data: PCM16 (int16) bytes to loop continuously.
		"""
		with self._lock:
			self._loop_data = data
			self._loop_pos = 0

	def clear_loop(self) -> None:
		"""Disable loop mode."""
		with self._lock:
			self._loop_data = None
			self._loop_pos = 0

	def stop_playback(self) -> None:
		"""Clear both the one-shot buffer and loop mode."""
		with self._lock:
			self._buffer = bytearray()
			self._loop_data = None
			self._loop_pos = 0

	def _callback(self, outdata, frames, time_info, status) -> None:
		"""Fill outdata with PCM16 audio: loop > one-shot > silence."""
		if status:
			log.warning("Output stream status: %s", status)
		bytes_needed = frames * self.channels * 2
		with self._lock:
			loop_data = self._loop_data
			if loop_data:
				# Loop mode: wrap-around without extra allocation
				total = len(loop_data)
				pos = self._loop_pos
				out = bytearray(bytes_needed)
				written = 0
				while written < bytes_needed:
					available = total - pos
					to_copy = min(available, bytes_needed - written)
					out[written : written + to_copy] = loop_data[
						pos : pos + to_copy
					]
					written += to_copy
					pos = (pos + to_copy) % total
				self._loop_pos = pos
				outdata[:] = bytes(out)
			elif self._buffer:
				# One-shot mode
				chunk = self._buffer[:bytes_needed]
				del self._buffer[:bytes_needed]
				if len(chunk) < bytes_needed:
					chunk = bytes(chunk) + b"\x00" * (bytes_needed - len(chunk))
				outdata[:] = bytes(chunk)
			else:
				# Silence
				outdata[:] = b"\x00" * bytes_needed


class AudioRecorder:
	"""Records microphone audio into a buffer and saves as WAV.

	Built on AudioInputStream.
	"""

	def __init__(
		self,
		sample_rate: int,
		channels: int,
		dtype: str = "int16",
		device: Optional[int] = None,
	) -> None:
		"""Initialise the recorder.

		Args:
			sample_rate: Sample rate in Hz.
			channels: Number of input channels.
			dtype: Data type string (currently always int16).
			device: sounddevice device index, or None for the system default.
		"""
		self.sample_rate = sample_rate
		self.channels = channels
		self.dtype = dtype
		self._stream = AudioInputStream(
			sample_rate, channels, self._accumulate, device
		)
		self._buffer = bytearray()
		self._stop_event = threading.Event()
		self._want_abort = False

	def record(self) -> None:
		"""Start capturing and block until stop() or abort() is called."""
		self._stream.start()
		self._stop_event.wait()
		self._stream.stop()

	def stop(self) -> None:
		"""Stop recording normally."""
		self._stop_event.set()

	def abort(self) -> None:
		"""Abort recording, discarding buffered audio."""
		self._want_abort = True
		self._stop_event.set()

	@property
	def was_aborted(self) -> bool:
		"""Whether the recording was aborted."""
		return self._want_abort

	def save_wav(self, path: str) -> None:
		"""Save buffered audio to a WAV file.

		Args:
			path: Destination file path.
		"""
		if self._want_abort:
			return
		with wave.open(path, "wb") as wav:
			wav.setnchannels(self.channels)
			wav.setsampwidth(2)  # 16-bit PCM
			wav.setframerate(self.sample_rate)
			wav.writeframes(bytes(self._buffer))

	@staticmethod
	def default_path() -> str:
		"""Return the default temporary WAV file path.

		Returns:
			Path string for the temporary recording file.
		"""
		return os.path.join(tempfile.gettempdir(), "basilisk_last_record.wav")

	def _accumulate(self, data: bytes) -> None:
		"""Append audio bytes to the buffer when not aborting.

		Args:
			data: Raw PCM16 bytes from the input stream.
		"""
		if not self._want_abort:
			self._buffer.extend(data)
