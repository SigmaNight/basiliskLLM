"""Central audio manager for BasiliskLLM."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from .sounds import SOUND_ALIASES, load_wav_as_pcm16
from .streams import AudioInputStream, AudioOutputStream, AudioRecorder

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
		"""Create a new output stream for voice sessions.

		Args:
			sample_rate: Sample rate in Hz.
			channels: Number of output channels.

		Returns:
			A new AudioOutputStream (not yet started).
		"""
		return AudioOutputStream(
			sample_rate=sample_rate,
			channels=channels,
			device=self._output_device,
		)

	def open_input_stream(
		self, sample_rate: int, channels: int, on_audio: Callable[[bytes], None]
	) -> AudioInputStream:
		"""Create a new input stream for voice sessions.

		Args:
			sample_rate: Sample rate in Hz.
			channels: Number of input channels.
			on_audio: Callback receiving PCM16 bytes.

		Returns:
			A new AudioInputStream (not yet started).
		"""
		return AudioInputStream(
			sample_rate=sample_rate,
			channels=channels,
			on_audio=on_audio,
			device=self._input_device,
		)

	def open_recorder(
		self, sample_rate: int, channels: int, dtype: str = "int16"
	) -> AudioRecorder:
		"""Create a new AudioRecorder using the configured input device.

		Args:
			sample_rate: Sample rate in Hz.
			channels: Number of input channels.
			dtype: Data type string (currently always int16).

		Returns:
			A new AudioRecorder (not yet recording).
		"""
		return AudioRecorder(
			sample_rate=sample_rate,
			channels=channels,
			dtype=dtype,
			device=self._input_device,
		)

	def cleanup(self) -> None:
		"""Stop and release the notification stream."""
		if self._notification_stream is not None:
			self._notification_stream.stop()
			self._notification_stream = None
