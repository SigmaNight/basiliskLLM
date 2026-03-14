"""Sound manager for playing sound effects in the application.

This module provides a centralized sound management system that handles:
- Loading and caching of sound files
- Asynchronous playback of sound effects
- Looped playback functionality
- Global sound management through singleton pattern

Playback is implemented with sounddevice.
"""

import logging
import threading
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from .global_vars import sounds_path

log = logging.getLogger(__name__)

ALIASES = {
	"chat_request_sent": sounds_path / "chat_request_sent.wav",
	"chat_response_pending": sounds_path / "chat_response_pending.wav",
	"chat_response_received": sounds_path / "chat_response_received.wav",
	"progress": sounds_path / "progress.wav",
	"recording_started": sounds_path / "recording_started.wav",
	"recording_stopped": sounds_path / "recording_stopped.wav",
}


class SoundManager:
	"""Manager class for playing sound effects.

	This class implements a thread-safe sound manager with caching capabilities.
	It supports both one-shot and looped playback of sound effects.
	"""

	def __init__(self):
		"""Initialize the sound manager.

		Sets up:
		- Sound cache for efficient playback
		- Threading support for looped playback
		- sounddevice OutputStream
		"""
		self.current_sound = None
		self.loop = False
		self.loop_thread = None
		self._stop_event = threading.Event()
		self._paused = False
		self._current_data: np.ndarray | None = None
		self._current_rate: int | None = None
		self._current_channels: int | None = None
		self._play_pos = 0
		self.thread_lock = threading.Lock()
		self.sound_cache: dict[Path, tuple[np.ndarray, int]] = {}

	def _ensure_sound_loaded(self, file_path: Path) -> tuple[np.ndarray, int]:
		"""Ensure that the sound file is loaded and cached.

		Args:
			file_path: Path to the sound file

		Returns:
			Loaded audio buffer and samplerate

		Raises:
			IOError: If the sound file could not be loaded
		"""
		if file_path in self.sound_cache:
			return self.sound_cache[file_path]
		try:
			data, samplerate = self._load_wav(file_path)
		except Exception as exc:
			raise IOError(f"Failed to load sound: {file_path}") from exc
		self.sound_cache[file_path] = (data, samplerate)
		return data, samplerate

	def _load_wav(self, file_path: Path) -> tuple[np.ndarray, int]:
		"""Load a WAV file into a float32 numpy array.

		Args:
			file_path: Path to the WAV file.

		Returns:
			Tuple of (audio_data, samplerate)

		Raises:
			ValueError: for incompatible sample width
		"""
		with wave.open(str(file_path), "rb") as wav:
			channels = wav.getnchannels()
			samplerate = wav.getframerate()
			sampwidth = wav.getsampwidth()
			frames = wav.readframes(wav.getnframes())

		if sampwidth == 1:
			data = np.frombuffer(frames, dtype=np.uint8)
			data = (data.astype(np.float32) - 128.0) / 128.0
		elif sampwidth == 2:
			data = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
			data /= 32768.0
		elif sampwidth == 3:
			raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
			signed = (
				raw[:, 0].astype(np.int32)
				| (raw[:, 1].astype(np.int32) << 8)
				| (raw[:, 2].astype(np.int32) << 16)
			)
			mask = signed & 0x800000
			signed = signed - (mask << 1)
			data = signed.astype(np.float32) / 8388608.0
		elif sampwidth == 4:
			data = np.frombuffer(frames, dtype=np.int32).astype(np.float32)
			data /= 2147483648.0
		else:
			raise ValueError(f"Unsupported sample width: {sampwidth}")

		if channels > 1:
			data = data.reshape(-1, channels)
		else:
			data = data.reshape(-1, 1)

		return data, samplerate

	def _stream_callback(
		self,
		outdata: np.ndarray,
		frames: int,
		time_info: dict,
		status: sd.CallbackFlags,
	) -> None:
		"""Sounddevice output stream callback for playback."""
		if status:
			log.warning("Audio stream status: %s", status)
		if self._stop_event.is_set() or self._current_data is None:
			outdata[:] = 0
			raise sd.CallbackStop

		data = self._current_data
		total_frames = data.shape[0]
		start = self._play_pos
		end = start + frames

		if self.loop:
			# Loop with wrap-around
			if end <= total_frames:
				outdata[:] = data[start:end]
				self._play_pos = end % total_frames
			else:
				first = data[start:total_frames]
				remaining = frames - first.shape[0]
				outdata[: first.shape[0]] = first
				loops = remaining // total_frames
				offset = first.shape[0]
				for _ in range(loops):
					outdata[offset : offset + total_frames] = data
					offset += total_frames
				tail = remaining % total_frames
				if tail:
					outdata[offset : offset + tail] = data[:tail]
				self._play_pos = tail
		else:
			if end <= total_frames:
				outdata[:] = data[start:end]
				self._play_pos = end
			else:
				available = max(total_frames - start, 0)
				if available:
					outdata[:available] = data[start:total_frames]
				if available < frames:
					outdata[available:] = 0
				self._play_pos = total_frames
				raise sd.CallbackStop

	def _play_sound_loop(
		self, data: np.ndarray, samplerate: int, start_pos: int = 0
	):
		"""Play a sound (looped or one-shot) using OutputStream.

		Args:
			data: Audio buffer.
			samplerate: Sample rate.
			start_pos: Frame index to start from (for resume after pause).
		"""
		self._current_data = data
		self._current_rate = samplerate
		self._current_channels = data.shape[1]
		self._play_pos = start_pos
		self._stop_event.clear()
		self._paused = False
		try:
			stream = sd.OutputStream(
				samplerate=samplerate,
				channels=data.shape[1],
				dtype="float32",
				callback=self._stream_callback,
			)
			with stream:
				while stream.active and not self._stop_event.is_set():
					time.sleep(0.05)
		except Exception as exc:
			log.error("Failed to play sound: %s", exc)
		finally:
			if not self._paused:
				self._current_data = None
				self._current_rate = None
				self._current_channels = None
				self._play_pos = 0

	def play_sound(self, file_path: str, loop: bool = False):
		"""Play a sound effect. If loop is True, the sound will be played in a loop.

		Args:
			file_path: Path to the sound file or a predefined alias from aliases mapping
			loop: Whether to play the sound in a loop
		"""
		with self.thread_lock:
			if file_path in ALIASES:
				file_path = ALIASES[file_path]

			self.stop_sound()

			try:
				data, samplerate = self._ensure_sound_loaded(file_path)
			except IOError as exc:
				log.error("%s", exc)
				return

			self.loop = loop

			self.loop_thread = threading.Thread(
				target=self._play_sound_loop,
				args=(data, samplerate),
				daemon=True,
			)
			self.loop_thread.start()

	def is_playing(self) -> bool:
		"""Return True if audio is currently playing."""
		return self.loop_thread is not None and self.loop_thread.is_alive()

	def is_paused(self) -> bool:
		"""Return True if audio is paused (stopped but retainable for resume)."""
		return self._paused and self._current_data is not None

	def pause_sound(self):
		"""Pause playback. Resume with resume_sound()."""
		with self.thread_lock:
			if not self.is_playing():
				return
			self._paused = True
			self._stop_event.set()
			try:
				sd.stop()
			except Exception:
				pass
			if self.loop_thread is not None:
				self.loop_thread.join(timeout=1)
				self.loop_thread = None
			self._stop_event.clear()

	def resume_sound(self):
		"""Resume playback from paused position."""
		with self.thread_lock:
			if not self.is_paused():
				return
			data = self._current_data
			rate = self._current_rate
			pos = self._play_pos
			if data is None or rate is None:
				return
			self._paused = False
			self.loop_thread = threading.Thread(
				target=self._play_sound_loop,
				args=(data, rate),
				kwargs={"start_pos": pos},
				daemon=True,
			)
			self.loop_thread.start()

	def stop_sound(self):
		"""Stop the currently playing sound effect (or clear paused state)."""
		self.loop = False
		self._paused = False
		self._stop_event.set()
		try:
			sd.stop()
		except Exception:
			pass
		if self.loop_thread is not None:
			self.loop_thread.join(timeout=1)
			self.loop_thread = None
		self._stop_event.clear()
		# Clear paused state so resume won't use stale data
		self._current_data = None
		self._current_rate = None
		self._current_channels = None
		self._play_pos = 0


sound_manager: SoundManager | None = None


def initialize_sound_manager():
	"""Initialize the global sound manager."""
	global sound_manager
	sound_manager = SoundManager()


def play_sound(file_path: str, loop: bool = False):
	"""Play a sound using the global sound manager. If loop is True, the sound will be played in a loop."""
	sound_manager.play_sound(file_path, loop)


def stop_sound():
	"""Stop the currently playing sound effect using the global sound manager."""
	sound_manager.stop_sound()


def is_playing() -> bool:
	"""Return True if audio is currently playing."""
	return sound_manager.is_playing()


def is_paused() -> bool:
	"""Return True if audio is paused."""
	return sound_manager.is_paused()


def pause_sound():
	"""Pause the currently playing sound. Resume with resume_sound()."""
	sound_manager.pause_sound()


def resume_sound():
	"""Resume playback from paused position."""
	sound_manager.resume_sound()
