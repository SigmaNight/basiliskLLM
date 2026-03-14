"""Utilities for playing audio from base64-encoded data."""

from __future__ import annotations

import base64
import logging
import tempfile

from basilisk.sound_manager import play_sound

log = logging.getLogger(__name__)

# sound_manager plays WAV via sounddevice. For other formats we'd need
# conversion. For now we only support WAV playback.
_SUPPORTED_PLAYBACK = {"wav"}


def play_audio_from_base64(data: str, format: str = "wav") -> None:
	"""Decode base64 audio, write to temp file, and play.

	Args:
		data: Base64-encoded audio bytes.
		format: Audio format (wav, mp3, etc). Only wav is supported for
			playback; other formats are stored but not played.
	"""
	if not data:
		return
	if format.lower() not in _SUPPORTED_PLAYBACK:
		log.debug(
			"Audio format %s not supported for playback; only wav supported",
			format,
		)
		return
	try:
		raw = base64.b64decode(data)
		suffix = f".{format}" if not format.startswith(".") else format
		with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
			tmp.write(raw)
			path = tmp.name
		play_sound(path)
		# Note: temp file is not deleted immediately since play_sound
		# returns before playback finishes. OS temp cleanup will remove it.
	except Exception as exc:
		log.error("Failed to play audio: %s", exc, exc_info=True)
