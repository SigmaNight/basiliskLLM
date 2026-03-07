"""Tests for basilisk.audio.sounds.load_wav_as_pcm16."""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import numpy as np
import pytest

from basilisk.audio.sounds import load_wav_as_pcm16


def _write_wav(
	path: Path,
	frames: bytes,
	sampwidth: int,
	channels: int = 1,
	rate: int = 16000,
) -> None:
	"""Write a synthetic WAV file."""
	with wave.open(str(path), "wb") as w:
		w.setnchannels(channels)
		w.setsampwidth(sampwidth)
		w.setframerate(rate)
		w.writeframes(frames)


class TestLoadWavAsPcm16:
	"""Tests for load_wav_as_pcm16."""

	def test_int16_passthrough(self, tmp_path):
		"""16-bit WAV is returned verbatim without conversion."""
		data = b"\x00\x10\x00\x20\x00\x30"
		wav_path = tmp_path / "test.wav"
		_write_wav(wav_path, data, sampwidth=2)
		pcm, rate, channels = load_wav_as_pcm16(wav_path)
		assert pcm == data
		assert rate == 16000
		assert channels == 1

	def test_uint8_converted_to_int16(self, tmp_path):
		"""8-bit WAV is converted to int16 PCM."""
		# Silence at 128 → should produce near-zero int16
		data = bytes([128, 128])
		wav_path = tmp_path / "test8.wav"
		_write_wav(wav_path, data, sampwidth=1)
		pcm, rate, channels = load_wav_as_pcm16(wav_path)
		assert len(pcm) == 4  # 2 samples × 2 bytes
		samples = np.frombuffer(pcm, dtype=np.int16)
		assert all(abs(int(s)) < 512 for s in samples)  # near zero

	def test_int32_converted_to_int16(self, tmp_path):
		"""32-bit WAV is converted to int16 PCM."""
		# Full-scale positive: 2147483647
		val = 2147483647
		frame = struct.pack("<i", val)
		wav_path = tmp_path / "test32.wav"
		_write_wav(wav_path, frame, sampwidth=4)
		pcm, rate, channels = load_wav_as_pcm16(wav_path)
		assert len(pcm) == 2
		sample = np.frombuffer(pcm, dtype=np.int16)[0]
		assert sample == 32767

	def test_stereo_int16_passthrough(self, tmp_path):
		"""Stereo 16-bit WAV is returned verbatim."""
		data = b"\x01\x00\x02\x00" * 4
		wav_path = tmp_path / "stereo.wav"
		_write_wav(wav_path, data, sampwidth=2, channels=2)
		pcm, rate, channels = load_wav_as_pcm16(wav_path)
		assert pcm == data
		assert channels == 2

	def test_unsupported_sampwidth_raises(self, tmp_path):
		"""8-byte sample width raises ValueError."""
		# We cannot easily write a true 8-byte WAV with the wave module,
		# so we patch wave.open instead.
		from unittest.mock import MagicMock, patch

		mock_wav = MagicMock()
		mock_wav.__enter__ = lambda s: s
		mock_wav.__exit__ = MagicMock(return_value=False)
		mock_wav.getnchannels.return_value = 1
		mock_wav.getframerate.return_value = 16000
		mock_wav.getsampwidth.return_value = 8
		mock_wav.getnframes.return_value = 0
		mock_wav.readframes.return_value = b""
		with patch("basilisk.audio.sounds.wave.open", return_value=mock_wav):
			with pytest.raises(ValueError, match="Unsupported"):
				load_wav_as_pcm16(Path("dummy.wav"))

	def test_sample_rate_and_channels_returned(self, tmp_path):
		"""Correct sample rate and channel count are returned."""
		data = b"\x00\x00" * 4
		wav_path = tmp_path / "meta.wav"
		_write_wav(wav_path, data, sampwidth=2, channels=1, rate=44100)
		pcm, rate, channels = load_wav_as_pcm16(wav_path)
		assert rate == 44100
		assert channels == 1
