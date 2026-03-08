"""Central audio manager for BasiliskLLM."""

from __future__ import annotations

import logging
import weakref
from pathlib import Path
from typing import Callable, Optional

from .sounds import SOUND_ALIASES, load_wav_as_pcm16
from .streams import (
	AudioInputStream,
	AudioOutputStream,
	AudioRecorder,
	_BaseAudioStream,
)

log = logging.getLogger(__name__)


class AudioManager:
	"""Central access point for all audio operations.

	Owns a persistent notification output stream for WAV playback, and
	provides factory methods for voice-session streams and recorders.
	"""

	def __init__(
		self,
		input_device: Optional[int] = None,
		output_device: Optional[int] = None,
	) -> None:
		"""Initialise the audio manager.

		Args:
			input_device: Default input device index, or None for system default.
			output_device: Default output device index, or None for system default.
		"""
		self._input_device = input_device
		self._output_device = output_device
		self._notification_stream: Optional[AudioOutputStream] = None
		self._wav_cache: dict[Path, tuple[bytes, int, int]] = {}
		self._streams: weakref.WeakSet[_BaseAudioStream] = weakref.WeakSet()
		self._recorders: weakref.WeakSet[AudioRecorder] = weakref.WeakSet()

	def set_input_device(self, device: Optional[int]) -> None:
		"""Set the default input device.

		Args:
			device: sounddevice device index, or None for system default.
		"""
		self._input_device = device

	def set_output_device(self, device: Optional[int]) -> None:
		"""Set the default output device, restarting the notification stream if active.

		Args:
			device: sounddevice device index, or None for system default.
		"""
		self._output_device = device
		if self._notification_stream is not None:
			old = self._notification_stream
			self._notification_stream = None
			old.stop()

	def play(self, sound: str, loop: bool = False) -> None:
		"""Play a named sound effect.

		Args:
			sound: Sound alias or file path string.
			loop: If True, play in a continuous loop until stop() is called.
		"""
		path = SOUND_ALIASES.get(sound)
		if path is None:
			path = Path(sound)
		if path not in self._wav_cache:
			try:
				self._wav_cache[path] = load_wav_as_pcm16(path)
			except Exception:
				log.error("Failed to load sound: %s", path, exc_info=True)
				return
		pcm16_bytes, sample_rate, channels = self._wav_cache[path]
		if (
			self._notification_stream is None
			or self._notification_stream.sample_rate != sample_rate
			or self._notification_stream.channels != channels
		):
			if self._notification_stream is not None:
				self._notification_stream.stop()
			self._notification_stream = AudioOutputStream(
				sample_rate=sample_rate,
				channels=channels,
				device=self._output_device,
			)
			try:
				self._notification_stream.start()
			except Exception:
				log.error("Failed to start notification stream", exc_info=True)
				self._notification_stream = None
				return
		self._notification_stream.stop_playback()
		if loop:
			self._notification_stream.set_loop(pcm16_bytes)
		else:
			self._notification_stream.enqueue(pcm16_bytes)

	def stop(self) -> None:
		"""Stop any currently playing notification sound."""
		if self._notification_stream is not None:
			self._notification_stream.stop_playback()

	def open_output_stream(
		self, sample_rate: int, channels: int = 1
	) -> AudioOutputStream:
		"""Create and track a new output stream.

		Args:
			sample_rate: Sample rate in Hz.
			channels: Number of output channels.

		Returns:
			A new AudioOutputStream (not yet started).
		"""
		stream = AudioOutputStream(
			sample_rate=sample_rate,
			channels=channels,
			device=self._output_device,
		)
		self._streams.add(stream)
		return stream

	def open_input_stream(
		self, sample_rate: int, channels: int, on_audio: Callable[[bytes], None]
	) -> AudioInputStream:
		"""Create and track a new input stream.

		Args:
			sample_rate: Sample rate in Hz.
			channels: Number of input channels.
			on_audio: Callback receiving PCM16 bytes.

		Returns:
			A new AudioInputStream (not yet started).
		"""
		stream = AudioInputStream(
			sample_rate=sample_rate,
			channels=channels,
			on_audio=on_audio,
			device=self._input_device,
		)
		self._streams.add(stream)
		return stream

	def open_recorder(
		self, sample_rate: int, channels: int, dtype: str = "int16"
	) -> AudioRecorder:
		"""Create and track a new AudioRecorder.

		Args:
			sample_rate: Sample rate in Hz.
			channels: Number of input channels.
			dtype: Data type string (currently always int16).

		Returns:
			A new AudioRecorder (not yet recording).
		"""
		recorder = AudioRecorder(
			sample_rate=sample_rate,
			channels=channels,
			dtype=dtype,
			device=self._input_device,
		)
		self._recorders.add(recorder)
		return recorder

	def close_stream(self, stream: _BaseAudioStream) -> None:
		"""Stop a managed stream and remove it from tracking.

		Args:
			stream: Stream previously returned by open_output_stream()
				or open_input_stream().
		"""
		stream.stop()
		self._streams.discard(stream)

	def close_recorder(
		self, recorder: AudioRecorder, abort: bool = False
	) -> None:
		"""Stop (or abort) a managed recorder and remove it from tracking.

		Args:
			recorder: Recorder previously returned by open_recorder().
			abort: If True, abort and discard buffered audio; otherwise
				stop normally.
		"""
		if abort:
			recorder.abort()
		else:
			recorder.stop()
		self._recorders.discard(recorder)

	def cleanup(self) -> None:
		"""Stop and release all managed streams, recorders, and the notification stream."""
		for stream in list(self._streams):
			stream.stop()
		self._streams = weakref.WeakSet()
		for recorder in list(self._recorders):
			recorder.abort()
		self._recorders = weakref.WeakSet()
		if self._notification_stream is not None:
			self._notification_stream.stop()
			self._notification_stream = None
