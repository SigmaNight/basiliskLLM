from __future__ import annotations

import logging
import os
import tempfile
import threading
import wave
from typing import TYPE_CHECKING

import sounddevice as sd
import wx
from numpy import append as np_append
from numpy import array as np_array

if TYPE_CHECKING:
	from basilisk.config.main_config import RecordingsSettings
	from basilisk.gui.conversation_tab import ConversationTab

	from .provider_engine.base_engine import BaseEngine

log = logging.getLogger(__name__)


class RecordingThread(threading.Thread):
	def __init__(
		self,
		provider_engine: BaseEngine,
		recordings_settings: RecordingsSettings,
		conversation_tab: ConversationTab,
		audio_file_path=None,
		response_format: str = "json",
	):
		super(RecordingThread, self).__init__()
		if not provider_engine:
			raise ValueError("No provider engine provided.")
		if not recordings_settings:
			raise ValueError("No recordings settings provided.")
		self.provider_engine = provider_engine
		self.audio_file_path = audio_file_path
		self.recordings_settings = recordings_settings
		self.response_format = response_format
		self.conversation_tab = conversation_tab
		self.daemon = True
		self._recording = False
		self._stop_record = False
		self._want_abort = False

	def run(self):
		if not self.audio_file_path:
			self.audio_file_path = self.get_filename()
			self.audio_data = np_array([], dtype=self.recordings_settings.dtype)
			log.debug("Recording started")
			wx.CallAfter(self.conversation_tab.on_recording_started)
			self.record_audio(self.recordings_settings.sample_rate)
			wx.CallAfter(self.conversation_tab.on_recording_stopped)
			log.debug("Recording stopped")

			if self._want_abort:
				return
			self.save_wav(
				self.audio_file_path,
				self.audio_data,
				self.recordings_settings.sample_rate,
			)
			log.debug("Audio file saved to %s", self.audio_file_path)
		wx.CallAfter(self.conversation_tab.on_transcription_started)
		self.process_transcription(self.audio_file_path)

	def record_audio(self, sampleRate: int):
		chunk_size = 1024
		self._recording = True
		with sd.InputStream(
			samplerate=sampleRate,
			channels=self.recordings_settings.channels,
			dtype=self.recordings_settings.dtype,
		) as stream:
			while not self._stop_record and self._recording:
				frame, overflowed = stream.read(chunk_size)
				if overflowed:
					log.error("Audio buffer has overflowed.")
				self.audio_data = np_append(self.audio_data, frame)
				if self._want_abort:
					break
		self._recording = False

	def save_wav(self, filename: str, data, sample_rate: int):
		if self._want_abort:
			return
		wavefile = wave.open(filename, "wb")
		wavefile.setnchannels(self.recordings_settings.channels)
		wavefile.setsampwidth(2)  # 16 bits
		wavefile.setframerate(sample_rate)
		wavefile.writeframes(data.tobytes())
		wavefile.close()

	def stop(self):
		self._stop_record = True
		self._recording = False

	def get_filename(self):
		return os.path.join(tempfile.gettempdir(), "basilisk_last_record.wav")

	def process_transcription(self, audio_file_path: str):
		if self._want_abort:
			return
		try:
			log.debug("Getting transcription from audio file")
			transcription = self.provider_engine.get_transcription(
				audio_file_path=audio_file_path,
				response_format=self.response_format,
			)
			if self._want_abort:
				return
			wx.CallAfter(
				self.conversation_tab.on_transcription_received, transcription
			)
		except BaseException as err:
			log.error(f"Error getting transcription: {err}")
			wx.CallAfter(self.conversation_tab.on_transcription_error, str(err))

	def abort(self):
		self._stop_record = True
		self._want_abort = True
