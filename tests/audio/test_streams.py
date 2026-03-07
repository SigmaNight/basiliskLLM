"""Tests for basilisk.audio.streams (mock sounddevice — no hardware)."""

from __future__ import annotations

import threading
import wave
from unittest.mock import MagicMock, patch

from basilisk.audio.streams import (
	AudioInputStream,
	AudioOutputStream,
	AudioRecorder,
	_BaseAudioStream,
)

# ---------------------------------------------------------------------------
# _BaseAudioStream
# ---------------------------------------------------------------------------


class TestBaseAudioStream:
	"""Tests for _BaseAudioStream lifecycle."""

	def test_initial_state(self):
		"""Stream starts as None."""

		class Concrete(_BaseAudioStream):
			"""Concrete subclass for testing."""

			def _create_stream(self):
				"""Return a mock stream."""
				return MagicMock()

		obj = Concrete()
		assert obj._stream is None

	def test_start_creates_and_starts_stream(self):
		"""start() calls _create_stream and stream.start()."""
		mock_stream = MagicMock()

		class Concrete(_BaseAudioStream):
			"""Concrete subclass for testing."""

			def _create_stream(self):
				"""Return mock stream."""
				return mock_stream

		obj = Concrete()
		obj.start()
		mock_stream.start.assert_called_once()
		assert obj._stream is mock_stream

	def test_start_idempotent(self):
		"""start() called twice does not create a second stream."""
		create_count = {"n": 0}

		class Concrete(_BaseAudioStream):
			"""Concrete subclass for testing."""

			def _create_stream(self):
				"""Count and return mock stream."""
				create_count["n"] += 1
				return MagicMock()

		obj = Concrete()
		obj.start()
		obj.start()
		assert create_count["n"] == 1

	def test_stop_closes_stream(self):
		"""stop() stops and closes the stream."""
		mock_stream = MagicMock()

		class Concrete(_BaseAudioStream):
			"""Concrete subclass for testing."""

			def _create_stream(self):
				"""Return mock stream."""
				return mock_stream

		obj = Concrete()
		obj.start()
		obj.stop()
		mock_stream.stop.assert_called_once()
		mock_stream.close.assert_called_once()
		assert obj._stream is None

	def test_stop_when_no_stream_is_noop(self):
		"""stop() when stream is None does not raise."""

		class Concrete(_BaseAudioStream):
			"""Concrete subclass for testing."""

			def _create_stream(self):
				"""Return mock stream."""
				return MagicMock()

		obj = Concrete()
		obj.stop()  # Should not raise


# ---------------------------------------------------------------------------
# AudioInputStream
# ---------------------------------------------------------------------------


class TestAudioInputStream:
	"""Tests for AudioInputStream (no hardware)."""

	def test_initial_state(self):
		"""Stream is None and callback is stored on construction."""
		cb = MagicMock()
		stream = AudioInputStream(sample_rate=16000, channels=1, on_audio=cb)
		assert stream._stream is None
		assert stream._on_audio is cb
		assert stream.sample_rate == 16000
		assert stream.channels == 1
		assert stream._device is None

	def test_device_stored(self):
		"""Device parameter is stored."""
		stream = AudioInputStream(
			sample_rate=16000, channels=1, on_audio=MagicMock(), device=3
		)
		assert stream._device == 3

	def test_callback_invokes_on_audio(self):
		"""_callback converts indata to bytes and calls on_audio."""
		cb = MagicMock()
		stream = AudioInputStream(sample_rate=16000, channels=1, on_audio=cb)
		indata = MagicMock()
		indata.tobytes.return_value = b"\x01\x02"
		stream._callback(indata, 1, None, None)
		cb.assert_called_once_with(b"\x01\x02")

	def test_stop_when_no_stream_is_noop(self):
		"""stop() is a no-op when no stream is open."""
		stream = AudioInputStream(
			sample_rate=16000, channels=1, on_audio=MagicMock()
		)
		stream.stop()  # Should not raise

	def test_create_stream_uses_int16(self, mocker):
		"""_create_stream uses dtype int16."""
		mock_sd_stream = MagicMock()
		mocker.patch(
			"basilisk.audio.streams.sd.InputStream", return_value=mock_sd_stream
		)
		stream = AudioInputStream(
			sample_rate=16000, channels=1, on_audio=MagicMock()
		)
		stream._create_stream()
		import basilisk.audio.streams as streams_mod

		streams_mod.sd.InputStream.assert_called_once_with(
			samplerate=16000,
			channels=1,
			dtype="int16",
			device=None,
			callback=stream._callback,
		)


# ---------------------------------------------------------------------------
# AudioOutputStream
# ---------------------------------------------------------------------------


class TestAudioOutputStream:
	"""Tests for AudioOutputStream buffer logic (no hardware)."""

	def test_initial_state(self):
		"""Buffer and loop data are empty on construction."""
		s = AudioOutputStream(sample_rate=24000)
		assert len(s._buffer) == 0
		assert s._stream is None
		assert s._loop_data is None
		assert s._loop_pos == 0

	def test_enqueue_adds_to_buffer(self):
		"""enqueue() appends bytes to the one-shot buffer."""
		s = AudioOutputStream(sample_rate=24000)
		s.enqueue(b"\x01\x02\x03\x04")
		assert s._buffer == bytearray(b"\x01\x02\x03\x04")

	def test_enqueue_empty_data_ignored(self):
		"""enqueue() with empty bytes does nothing."""
		s = AudioOutputStream(sample_rate=24000)
		s.enqueue(b"")
		assert len(s._buffer) == 0

	def test_enqueue_accumulates(self):
		"""Multiple enqueue() calls accumulate data."""
		s = AudioOutputStream(sample_rate=24000)
		s.enqueue(b"\x01\x02")
		s.enqueue(b"\x03\x04")
		assert s._buffer == bytearray(b"\x01\x02\x03\x04")

	def test_clear_empties_buffer(self):
		"""clear() resets the one-shot buffer."""
		s = AudioOutputStream(sample_rate=24000)
		s.enqueue(b"\x01\x02\x03\x04")
		s.clear()
		assert len(s._buffer) == 0

	def test_set_loop_stores_data(self):
		"""set_loop() stores loop data and resets position."""
		s = AudioOutputStream(sample_rate=24000)
		s._loop_pos = 10
		s.set_loop(b"\xaa\xbb")
		assert s._loop_data == b"\xaa\xbb"
		assert s._loop_pos == 0

	def test_clear_loop_removes_data(self):
		"""clear_loop() removes loop data."""
		s = AudioOutputStream(sample_rate=24000)
		s.set_loop(b"\xaa\xbb")
		s.clear_loop()
		assert s._loop_data is None
		assert s._loop_pos == 0

	def test_stop_playback_clears_both(self):
		"""stop_playback() clears buffer and loop data atomically."""
		s = AudioOutputStream(sample_rate=24000)
		s.enqueue(b"\x01\x02")
		s.set_loop(b"\xaa\xbb")
		s.stop_playback()
		assert len(s._buffer) == 0
		assert s._loop_data is None

	# -- _callback: one-shot ---------------------------------------------------

	def test_callback_full_buffer(self):
		"""_callback() drains exactly the requested bytes."""
		s = AudioOutputStream(sample_rate=24000, channels=1)
		# 4 frames × 1 channel × 2 bytes = 8 bytes
		s.enqueue(b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a")
		outdata = bytearray(8)
		s._callback(outdata, 4, None, None)
		assert bytes(outdata) == b"\x01\x02\x03\x04\x05\x06\x07\x08"
		assert s._buffer == bytearray(b"\x09\x0a")

	def test_callback_partial_buffer_pads_zeros(self):
		"""_callback() pads with zeros when buffer has fewer bytes than needed."""
		s = AudioOutputStream(sample_rate=24000, channels=1)
		s.enqueue(b"\x01\x02")
		outdata = bytearray(8)
		s._callback(outdata, 4, None, None)
		assert bytes(outdata) == b"\x01\x02\x00\x00\x00\x00\x00\x00"
		assert len(s._buffer) == 0

	def test_callback_empty_buffer_all_zeros(self):
		"""_callback() fills with zeros when buffer is empty."""
		s = AudioOutputStream(sample_rate=24000, channels=1)
		outdata = bytearray(8)
		s._callback(outdata, 4, None, None)
		assert bytes(outdata) == b"\x00" * 8

	# -- _callback: loop -------------------------------------------------------

	def test_callback_loop_exact_fit(self):
		"""Loop callback fills outdata when loop data fits exactly."""
		s = AudioOutputStream(sample_rate=24000, channels=1)
		# 4 frames × 2 bytes = 8 bytes loop data
		loop = bytes(range(8))
		s.set_loop(loop)
		outdata = bytearray(8)
		s._callback(outdata, 4, None, None)
		assert bytes(outdata) == loop
		assert s._loop_pos == 0  # wrapped around

	def test_callback_loop_wrap_around(self):
		"""Loop callback wraps around when loop data is shorter than needed."""
		s = AudioOutputStream(sample_rate=24000, channels=1)
		# 4-byte loop, need 8 bytes → wraps twice
		loop = b"\x01\x02\x03\x04"
		s.set_loop(loop)
		outdata = bytearray(8)
		s._callback(outdata, 4, None, None)
		assert bytes(outdata) == loop + loop

	def test_callback_loop_takes_priority_over_one_shot(self):
		"""Loop mode takes priority over one-shot buffer."""
		s = AudioOutputStream(sample_rate=24000, channels=1)
		s.enqueue(b"\xff\xff\xff\xff\xff\xff\xff\xff")
		loop = b"\x01\x02\x01\x02\x01\x02\x01\x02"
		s.set_loop(loop)
		outdata = bytearray(8)
		s._callback(outdata, 4, None, None)
		assert bytes(outdata) == loop


# ---------------------------------------------------------------------------
# AudioRecorder
# ---------------------------------------------------------------------------


class TestAudioRecorder:
	"""Tests for AudioRecorder (mock AudioInputStream)."""

	def test_initial_state(self):
		"""Recorder starts with empty buffer and no abort."""
		with patch("basilisk.audio.streams.AudioInputStream") as MockStream:
			MockStream.return_value = MagicMock()
			rec = AudioRecorder(sample_rate=16000, channels=1)
		assert len(rec._buffer) == 0
		assert not rec.was_aborted
		assert not rec._stop_event.is_set()

	def test_accumulate_appends_data(self):
		"""_accumulate() appends bytes to buffer when not aborted."""
		with patch("basilisk.audio.streams.AudioInputStream"):
			rec = AudioRecorder(sample_rate=16000, channels=1)
		rec._accumulate(b"\x01\x02")
		rec._accumulate(b"\x03\x04")
		assert rec._buffer == bytearray(b"\x01\x02\x03\x04")

	def test_accumulate_ignored_after_abort(self):
		"""_accumulate() ignores data after abort."""
		with patch("basilisk.audio.streams.AudioInputStream"):
			rec = AudioRecorder(sample_rate=16000, channels=1)
		rec._want_abort = True
		rec._accumulate(b"\x01\x02")
		assert len(rec._buffer) == 0

	def test_stop_sets_event(self):
		"""stop() signals the stop event."""
		with patch("basilisk.audio.streams.AudioInputStream"):
			rec = AudioRecorder(sample_rate=16000, channels=1)
		rec.stop()
		assert rec._stop_event.is_set()
		assert not rec.was_aborted

	def test_abort_sets_flag_and_event(self):
		"""abort() sets want_abort and signals the stop event."""
		with patch("basilisk.audio.streams.AudioInputStream"):
			rec = AudioRecorder(sample_rate=16000, channels=1)
		rec.abort()
		assert rec.was_aborted
		assert rec._stop_event.is_set()

	def test_save_wav_writes_correct_file(self, tmp_path):
		"""save_wav() writes a valid WAV with buffered data."""
		with patch("basilisk.audio.streams.AudioInputStream"):
			rec = AudioRecorder(sample_rate=16000, channels=1)
		# 4 int16 samples
		data = b"\x01\x00\x02\x00\x03\x00\x04\x00"
		rec._buffer = bytearray(data)
		out = str(tmp_path / "test.wav")
		rec.save_wav(out)
		with wave.open(out, "rb") as w:
			assert w.getnchannels() == 1
			assert w.getframerate() == 16000
			assert w.getsampwidth() == 2
			assert w.readframes(4) == data

	def test_save_wav_skipped_when_aborted(self, tmp_path):
		"""save_wav() does nothing when aborted."""
		with patch("basilisk.audio.streams.AudioInputStream"):
			rec = AudioRecorder(sample_rate=16000, channels=1)
		rec._want_abort = True
		out = str(tmp_path / "test.wav")
		rec.save_wav(out)
		assert not (tmp_path / "test.wav").exists()

	def test_default_path_returns_string(self):
		"""default_path() returns a non-empty string."""
		path = AudioRecorder.default_path()
		assert isinstance(path, str)
		assert path.endswith(".wav")

	def test_record_blocks_until_stop(self):
		"""record() blocks until stop() is called from another thread."""
		mock_inner_stream = MagicMock()
		with patch(
			"basilisk.audio.streams.AudioInputStream",
			return_value=mock_inner_stream,
		):
			rec = AudioRecorder(sample_rate=16000, channels=1)

		results = []

		def stopper():
			rec.stop()

		t = threading.Thread(target=stopper)
		t.start()
		rec.record()  # should unblock when stopper fires
		results.append("done")
		t.join()
		assert results == ["done"]
		mock_inner_stream.start.assert_called_once()
		mock_inner_stream.stop.assert_called_once()
