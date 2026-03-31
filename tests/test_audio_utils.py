"""Tests for audio_utils."""

import base64
from unittest.mock import patch

from basilisk.audio_utils import play_audio_from_base64


class TestPlayAudioFromBase64:
	"""Tests for play_audio_from_base64."""

	def test_empty_data_returns_early(self):
		"""Empty or falsy data returns without calling play_sound."""
		with patch("basilisk.audio_utils.play_sound") as mock_play:
			play_audio_from_base64("")
			play_audio_from_base64(None)
			mock_play.assert_not_called()

	def test_mp3_opens_with_default_app_not_play_sound(self):
		"""MP3 (e.g. Lyria) is opened via OS handler, not in-process WAV player."""
		data = base64.b64encode(b"fake mp3").decode()
		with patch("basilisk.audio_utils.stop_sound") as mock_stop:
			with patch("basilisk.audio_utils.play_sound") as mock_play:
				with patch(
					"basilisk.audio_utils._play_file_with_default_app"
				) as mock_ext:
					play_audio_from_base64(data, "mp3")
			mock_stop.assert_called_once()
			mock_play.assert_not_called()
			mock_ext.assert_called_once()

	def test_wav_calls_play_sound_with_temp_file(self):
		"""WAV data is decoded, written to temp file, and play_sound called."""
		raw = b"fake wav bytes"
		data = base64.b64encode(raw).decode()
		with patch("basilisk.audio_utils.stop_sound") as mock_stop:
			with patch("basilisk.audio_utils.play_sound") as mock_play:
				play_audio_from_base64(data, "wav")
			mock_stop.assert_called_once()
			mock_play.assert_called_once()
			path = mock_play.call_args[0][0]
			assert path.endswith(".wav")
			with open(path, "rb") as f:
				assert f.read() == raw

	def test_invalid_base64_does_not_raise(self):
		"""Invalid base64 data is caught and does not raise; play_sound not called."""
		with patch("basilisk.audio_utils.stop_sound"):
			with patch("basilisk.audio_utils.play_sound") as mock_play:
				play_audio_from_base64("not-valid-base64!!", "wav")
				mock_play.assert_not_called()
