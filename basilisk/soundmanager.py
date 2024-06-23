import logging
import time
import wx
import wx.adv
import threading
from pathlib import Path
from .globalvars import resource_path

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
		self.current_sound = None
		self.loop = False
		self.loop_thread = None
		self.sound_player = wx.adv.Sound()
		self.thread_lock = threading.Lock()
		self.sound_cache = {}

	def _ensure_sound_loaded(self, file_path) -> wx.adv.Sound:
		if file_path not in self.sound_cache:
			sound = wx.adv.Sound()
			if sound.Create(str(file_path)):
				self.sound_cache[file_path] = sound
			else:
				raise IOError(f"Failed to load sound: {file_path}")
		return self.sound_cache[file_path]

	def _play_sound_loop(self, sound: wx.adv.Sound, delay: float = 0.1):
		while self.loop:
			sound.Play(wx.adv.SOUND_ASYNC | wx.adv.SOUND_LOOP)
			while self.loop:
				time.sleep(delay)
			sound.Stop()

	def play_sound(self, file_path: str, loop: bool = False):
		with self.thread_lock:
			if file_path in ALIASES:
				file_path = ALIASES[file_path]

			self.stop_sound()

			sound = self._ensure_sound_loaded(file_path)

			self.loop = loop

			if loop:
				self.loop_thread = threading.Thread(
					target=self._play_sound_loop, args=(sound,)
				)
				self.loop_thread.daemon = True
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


def play_sound(file_path: str, loop: bool = False):
	sound_manager.play_sound(file_path, loop)


def stop_sound():
	sound_manager.stop_sound()
