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
	def __init__(self):
		self.current_sound: wx.adv.Sound = None
		self.loop = False
		self.loop_thread = None
		self.sound_player = wx.adv.Sound()
		self.thread_lock = threading.Lock()
		self.sound_cache = {}

	def _ensure_sound_loaded(self, file_source) -> wx.adv.Sound:
		if isinstance(file_source, bytes):
			sound = wx.adv.Sound()
			sound.CreateFromData(file_source)
			return sound
		if file_source not in self.sound_cache:
			sound = wx.adv.Sound()
			if sound.Create(str(file_source)):
				self.sound_cache[file_source] = sound
			else:
				raise IOError(f"Failed to load sound: {file_source}")
		return self.sound_cache[file_source]

	def _play_sound_loop(self, sound: wx.adv.Sound, delay: float = 0.1):
		while self.loop:
			sound.Play(wx.adv.SOUND_ASYNC | wx.adv.SOUND_LOOP)

			while self.loop:
				time.sleep(delay)
			sound.Stop()

	def play_sound(self, file: str | Path | bytes, loop: bool = False):
		with self.thread_lock:
			if isinstance(file, str) and file in ALIASES:
				file = ALIASES[file]

			self.stop_sound()

			sound = self._ensure_sound_loaded(file)

			self.loop = loop

			if loop:
				self.loop_thread = threading.Thread(
					target=self._play_sound_loop, args=(sound,), daemon=True
				)
				self.loop_thread.start()
			else:
				sound.Play(wx.adv.SOUND_ASYNC)

	def stop_sound(self):
		self.loop = False
		if self.loop_thread is not None:
			self.loop_thread.join(timeout=1)
			self.loop_thread = None


def initialize_sound_manager():
	global sound_manager
	sound_manager = SoundManager()


def play_sound(file: str | Path | bytes, loop: bool = False):
	sound_manager.play_sound(file, loop)


def stop_sound():
	sound_manager.stop_sound()
