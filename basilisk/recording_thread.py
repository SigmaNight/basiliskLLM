"""Module for handling audio recording and transcription in a separate thread.

This module provides functionality to record audio, save it as a WAV file,
and process the recording for transcription using a provided engine.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Optional

import wx

if TYPE_CHECKING:
	from basilisk.audio.streams import AudioRecorder
	from basilisk.config.main_config import RecordingsSettings
	from basilisk.presenters.conversation_presenter import ConversationPresenter

	from .provider_engine.base_engine import BaseEngine

log = logging.getLogger(__name__)


class RecordingThread(threading.Thread):
	"""Thread class for handling audio recording and transcription.

	This class manages the recording of audio input, saves it to a WAV file,
	and processes it for transcription using a provided engine.
	"""

	def __init__(
		self,
		provider_engine: BaseEngine,
		recordings_settings: RecordingsSettings,
		callbacks: ConversationPresenter,
		audio_file_path=None,
		response_format: str = "json",
		# Legacy alias for backwards compatibility
		conversation_tab=None,
	):
		"""Initialize the recording thread.

		Args:
			provider_engine: Engine to handle audio transcription.
			recordings_settings: Configuration for audio recording.
			callbacks: Object providing recording callback methods.
			audio_file_path: Path to existing audio file. Defaults to None.
			response_format: Format for transcription response. Defaults to "json".
			conversation_tab: Deprecated alias for callbacks.

		Raises:
			ValueError: If provider_engine or recordings_settings are not provided.
		"""
		super(RecordingThread, self).__init__()
		if not provider_engine:
			raise ValueError("No provider engine provided.")
		if not recordings_settings:
			raise ValueError("No recordings settings provided.")
		self.provider_engine = provider_engine
		self.audio_file_path = audio_file_path
		self.recordings_settings = recordings_settings
		self.response_format = response_format
		self.callbacks = callbacks or conversation_tab
		self.daemon = True
		self._recorder: Optional[AudioRecorder] = None
		self._want_abort = False

	def run(self):
		"""Execute the recording and transcription process.

		Records audio if no existing file is provided, saves it to a WAV file,
		and processes it for transcription. Updates the GUI with status changes.
		"""
		if not self.audio_file_path:
			import basilisk.audio as audio
			from basilisk.audio.streams import AudioRecorder

			self.audio_file_path = AudioRecorder.default_path()
			self._recorder = audio.get_manager().open_recorder(
				self.recordings_settings.sample_rate,
				self.recordings_settings.channels,
				self.recordings_settings.dtype,
			)
			# If abort() was called before the recorder was created, propagate it
			if self._want_abort:
				self._recorder.abort()
			else:
				wx.CallAfter(self.callbacks.on_recording_started)
			log.debug("Recording started")
			self._recorder.record()  # blocks until stop() or abort()
			if self._recorder.was_aborted:
				return
			wx.CallAfter(self.callbacks.on_recording_stopped)
			log.debug("Recording stopped")
			self._recorder.save_wav(self.audio_file_path)
			log.debug("Audio file saved to %s", self.audio_file_path)

		if self._want_abort:
			return
		wx.CallAfter(self.callbacks.on_transcription_started)
		self.process_transcription(self.audio_file_path)

	def stop(self):
		"""Stop the current recording process."""
		if self._recorder is not None:
			self._recorder.stop()

	def abort(self):
		"""Abort the recording and transcription process."""
		self._want_abort = True
		if self._recorder is not None:
			self._recorder.abort()

	def process_transcription(self, audio_file_path: str):
		"""Process the audio file for transcription.

		Args:
			audio_file_path: Path to the audio file to transcribe.
		"""
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
				self.callbacks.on_transcription_received, transcription
			)
		except BaseException as err:
			log.error("Error getting transcription: %s", err)
			wx.CallAfter(self.callbacks.on_transcription_error, str(err))
