"""Tests for basilisk.audio.manager.AudioManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from basilisk.audio.manager import AudioManager
from basilisk.audio.streams import (
	AudioInputStream,
	AudioOutputStream,
	AudioRecorder,
)


def _make_manager(**kwargs) -> AudioManager:
	"""Return an AudioManager with default settings."""
	return AudioManager(**kwargs)


class TestAudioManagerPlay:
	"""Tests for AudioManager.play()."""

	def test_play_loads_and_enqueues(self, mocker):
		"""play() loads WAV, creates stream, and enqueues bytes."""
		pcm = b"\x01\x02\x03\x04"
		mocker.patch(
			"basilisk.audio.manager.load_wav_as_pcm16",
			return_value=(pcm, 16000, 1),
		)
		mock_stream = MagicMock(spec=AudioOutputStream)
		mock_stream.sample_rate = 16000
		mock_stream.channels = 1
		mocker.patch(
			"basilisk.audio.manager.AudioOutputStream", return_value=mock_stream
		)
		mgr = _make_manager()
		mgr.play("recording_started")
		mock_stream.start.assert_called_once()
		mock_stream.stop_playback.assert_called_once()
		mock_stream.enqueue.assert_called_once_with(pcm)
		mock_stream.set_loop.assert_not_called()

	def test_play_loop_uses_set_loop(self, mocker):
		"""play(..., loop=True) calls set_loop instead of enqueue."""
		pcm = b"\xaa\xbb"
		mocker.patch(
			"basilisk.audio.manager.load_wav_as_pcm16",
			return_value=(pcm, 16000, 1),
		)
		mock_stream = MagicMock(spec=AudioOutputStream)
		mock_stream.sample_rate = 16000
		mock_stream.channels = 1
		mocker.patch(
			"basilisk.audio.manager.AudioOutputStream", return_value=mock_stream
		)
		mgr = _make_manager()
		mgr.play("progress", loop=True)
		mock_stream.set_loop.assert_called_once_with(pcm)
		mock_stream.enqueue.assert_not_called()

	def test_play_reuses_existing_stream_same_format(self, mocker):
		"""play() reuses the notification stream when format matches."""
		pcm = b"\x00\x01"
		mocker.patch(
			"basilisk.audio.manager.load_wav_as_pcm16",
			return_value=(pcm, 16000, 1),
		)
		mock_stream = MagicMock(spec=AudioOutputStream)
		mock_stream.sample_rate = 16000
		mock_stream.channels = 1
		ctor = mocker.patch(
			"basilisk.audio.manager.AudioOutputStream", return_value=mock_stream
		)
		mgr = _make_manager()
		mgr.play("recording_started")
		mgr.play("recording_stopped")
		assert ctor.call_count == 1  # same stream reused

	def test_play_recreates_stream_on_format_change(self, mocker):
		"""play() creates a new stream when sample rate differs."""
		mocker.patch(
			"basilisk.audio.manager.load_wav_as_pcm16",
			side_effect=[(b"\x00", 16000, 1), (b"\x00", 44100, 1)],
		)
		mock_stream1 = MagicMock(spec=AudioOutputStream)
		mock_stream1.sample_rate = 16000
		mock_stream1.channels = 1
		mock_stream2 = MagicMock(spec=AudioOutputStream)
		mock_stream2.sample_rate = 44100
		mock_stream2.channels = 1
		ctor = mocker.patch(
			"basilisk.audio.manager.AudioOutputStream",
			side_effect=[mock_stream1, mock_stream2],
		)
		mgr = _make_manager()
		mgr.play("recording_started")
		mgr.play("recording_stopped")
		assert ctor.call_count == 2
		mock_stream1.stop.assert_called_once()

	def test_play_load_error_is_silent(self, mocker):
		"""play() logs error but does not raise when WAV load fails."""
		mocker.patch(
			"basilisk.audio.manager.load_wav_as_pcm16",
			side_effect=IOError("not found"),
		)
		mgr = _make_manager()
		mgr.play("recording_started")  # Should not raise

	def test_play_caches_wav(self, mocker):
		"""play() only calls load_wav_as_pcm16 once per unique path."""
		load_fn = mocker.patch(
			"basilisk.audio.manager.load_wav_as_pcm16",
			return_value=(b"\x00", 16000, 1),
		)
		mock_stream = MagicMock(spec=AudioOutputStream)
		mock_stream.sample_rate = 16000
		mock_stream.channels = 1
		mocker.patch(
			"basilisk.audio.manager.AudioOutputStream", return_value=mock_stream
		)
		mgr = _make_manager()
		mgr.play("recording_started")
		mgr.play("recording_started")
		assert load_fn.call_count == 1


class TestAudioManagerStop:
	"""Tests for AudioManager.stop()."""

	def test_stop_calls_stop_playback(self, mocker):
		"""stop() calls stop_playback on the notification stream."""
		mocker.patch(
			"basilisk.audio.manager.load_wav_as_pcm16",
			return_value=(b"\x00", 16000, 1),
		)
		mock_stream = MagicMock(spec=AudioOutputStream)
		mock_stream.sample_rate = 16000
		mock_stream.channels = 1
		mocker.patch(
			"basilisk.audio.manager.AudioOutputStream", return_value=mock_stream
		)
		mgr = _make_manager()
		mgr.play("recording_started")
		mgr.stop()
		# stop_playback called once from play() setup + once from stop()
		assert mock_stream.stop_playback.call_count == 2

	def test_stop_when_no_stream_is_noop(self):
		"""stop() does nothing when no stream has been created."""
		mgr = _make_manager()
		mgr.stop()  # Should not raise


class TestAudioManagerDevices:
	"""Tests for device propagation in AudioManager."""

	def test_set_output_device_stops_stream(self, mocker):
		"""set_output_device() stops the existing notification stream."""
		mocker.patch(
			"basilisk.audio.manager.load_wav_as_pcm16",
			return_value=(b"\x00", 16000, 1),
		)
		mock_stream = MagicMock(spec=AudioOutputStream)
		mock_stream.sample_rate = 16000
		mock_stream.channels = 1
		mocker.patch(
			"basilisk.audio.manager.AudioOutputStream", return_value=mock_stream
		)
		mgr = _make_manager()
		mgr.play("recording_started")
		mgr.set_output_device(2)
		mock_stream.stop.assert_called_once()
		assert mgr._notification_stream is None
		assert mgr._output_device == 2

	def test_set_input_device_stored(self):
		"""set_input_device() stores the device index."""
		mgr = _make_manager()
		mgr.set_input_device(5)
		assert mgr._input_device == 5


class TestAudioManagerFactories:
	"""Tests for AudioManager open_* factory methods."""

	def test_open_output_stream_returns_audio_output_stream(self):
		"""open_output_stream() returns an AudioOutputStream."""
		mgr = _make_manager(output_device=1)
		stream = mgr.open_output_stream(sample_rate=24000, channels=1)
		assert isinstance(stream, AudioOutputStream)
		assert stream.sample_rate == 24000
		assert stream._device == 1

	def test_open_input_stream_returns_audio_input_stream(self):
		"""open_input_stream() returns an AudioInputStream."""
		cb = MagicMock()
		mgr = _make_manager(input_device=2)
		stream = mgr.open_input_stream(
			sample_rate=24000, channels=1, on_audio=cb
		)
		assert isinstance(stream, AudioInputStream)
		assert stream._on_audio is cb
		assert stream._device == 2

	def test_open_recorder_returns_audio_recorder(self):
		"""open_recorder() returns an AudioRecorder."""
		with patch("basilisk.audio.streams.AudioInputStream"):
			mgr = _make_manager(input_device=3)
			rec = mgr.open_recorder(sample_rate=16000, channels=1)
		assert isinstance(rec, AudioRecorder)
		assert rec.sample_rate == 16000


class TestAudioManagerCleanup:
	"""Tests for AudioManager.cleanup()."""

	def test_cleanup_stops_notification_stream(self, mocker):
		"""cleanup() stops and releases the notification stream."""
		mocker.patch(
			"basilisk.audio.manager.load_wav_as_pcm16",
			return_value=(b"\x00", 16000, 1),
		)
		mock_stream = MagicMock(spec=AudioOutputStream)
		mock_stream.sample_rate = 16000
		mock_stream.channels = 1
		mocker.patch(
			"basilisk.audio.manager.AudioOutputStream", return_value=mock_stream
		)
		mgr = _make_manager()
		mgr.play("recording_started")
		mgr.cleanup()
		mock_stream.stop.assert_called_once()
		assert mgr._notification_stream is None

	def test_cleanup_when_no_stream_is_noop(self):
		"""cleanup() does nothing when no stream was created."""
		mgr = _make_manager()
		mgr.cleanup()  # Should not raise
