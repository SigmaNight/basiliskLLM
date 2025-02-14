"""Sound manager for playing sound effects in the application.

This module provides a centralized sound management system that handles:
- Loading and caching of sound files
- Asynchronous playback of sound effects
- Looped playback functionality
- Global sound management through singleton pattern

Supported formats are determined by the wx.adv.Sound capabilities.
"""

import logging
import threading
import time
from pathlib import Path

import wx
import wx.adv

from .global_vars import resource_path

log = logging.getLogger(__name__)

ALIASES = {
	"chat_request_sent": resource_path
	/ Path("sounds", "chat_request_sent.wav"),
	"chat_response_pending": resource_path
	/ Path("sounds", "chat_response_pending.wav"),
	"chat_response_received": resource_path
	/ Path("sounds", "chat_response_received.wav"),
	"progress": resource_path / Path("sounds", "progress.wav"),
	"recording_started": resource_path
	/ Path("sounds", "recording_started.wav"),
	"recording_stopped": resource_path
	/ Path("sounds", "recording_stopped.wav"),
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
		- wx.adv.Sound player
		"""
		self.current_sound = None
		self.loop = False
		self.loop_thread = None
		self.sound_player = wx.adv.Sound()
		self.thread_lock = threading.Lock()
		self.sound_cache: dict[Path, wx.adv.Sound] = {}

	def _ensure_sound_loaded(self, file_path: Path) -> wx.adv.Sound:
		"""Ensure that the sound file is loaded and cached.

		Args:
			file_path: Path to the sound file

		Returns:
			Loaded wx.adv.Sound object

		Raises:
			IOError: If the sound file could not be loaded
		"""
		if file_path in self.sound_cache:
			return self.sound_cache[file_path]
		sound = wx.adv.Sound()
		if sound.Create(str(file_path)):
			self.sound_cache[file_path] = sound
		else:
			raise IOError(f"Failed to load sound: {file_path}")
		return sound

	def _play_sound_loop(self, sound: wx.adv.Sound, delay: float = 0.1):
		"""Play a sound in a loop until the loop flag is set to False.

		Args:
			sound: wx.adv.Sound object to play
			delay: Delay in seconds between sound repetitions to prevent CPU overload (default: 0.1)
		"""
		while self.loop:
			sound.Play(wx.adv.SOUND_ASYNC | wx.adv.SOUND_LOOP)
			while self.loop:
				time.sleep(delay)
			sound.Stop()

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

			sound = self._ensure_sound_loaded(file_path)

			self.loop = loop

			if loop:
				self.loop_thread = threading.Thread(
					target=self._play_sound_loop, args=(sound,), daemon=True
				)
				self.loop_thread.start()
			else:
				sound.Play(wx.adv.SOUND_ASYNC)

	def stop_sound(self):
		"""Stop the currently playing sound effect."""
		self.loop = False
		if self.loop_thread is not None:
			self.loop_thread.join(timeout=1)
			self.loop_thread = None


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
