"""Sound aliases and WAV-to-PCM16 loading for BasiliskLLM."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from basilisk.global_vars import sounds_path

SOUND_ALIASES: dict[str, Path] = {
	"chat_request_sent": sounds_path / "chat_request_sent.wav",
	"chat_response_pending": sounds_path / "chat_response_pending.wav",
	"chat_response_received": sounds_path / "chat_response_received.wav",
	"progress": sounds_path / "progress.wav",
	"recording_started": sounds_path / "recording_started.wav",
	"recording_stopped": sounds_path / "recording_stopped.wav",
}


def load_wav_as_pcm16(path: Path) -> tuple[bytes, int, int]:
	"""Load a WAV file and convert it to PCM16 (int16) bytes.

	Args:
		path: Path to the WAV file.

	Returns:
		Tuple of (pcm16_bytes, sample_rate, channels).

	Raises:
		ValueError: If the sample width is not supported.
	"""
	with wave.open(str(path), "rb") as wav:
		channels = wav.getnchannels()
		sample_rate = wav.getframerate()
		sampwidth = wav.getsampwidth()
		frames = wav.readframes(wav.getnframes())

	if sampwidth == 2:
		# Already int16 — return raw bytes directly
		return frames, sample_rate, channels

	# Convert via float32 intermediary
	if sampwidth == 1:
		data = np.frombuffer(frames, dtype=np.uint8)
		float_data = (data.astype(np.float32) - 128.0) / 128.0
	elif sampwidth == 3:
		raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
		signed = (
			raw[:, 0].astype(np.int32)
			| (raw[:, 1].astype(np.int32) << 8)
			| (raw[:, 2].astype(np.int32) << 16)
		)
		mask = signed & 0x800000
		signed = signed - (mask << 1)
		float_data = signed.astype(np.float32) / 8388608.0
	elif sampwidth == 4:
		data = np.frombuffer(frames, dtype=np.int32)
		float_data = data.astype(np.float32) / 2147483648.0
	else:
		raise ValueError(f"Unsupported sample width: {sampwidth}")

	int16_data = np.clip(float_data * 32768.0, -32768, 32767).astype(np.int16)
	return int16_data.tobytes(), sample_rate, channels
