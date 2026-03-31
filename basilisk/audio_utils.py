"""Utilities for playing audio from base64-encoded data."""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import sys
import tempfile

from basilisk.sound_manager import play_sound, stop_sound

log = logging.getLogger(__name__)

_WAV = frozenset({"wav"})
# Lyria 3 returns MP3 by default; open with the OS default handler.
_EXTERNAL = frozenset({"mp3", "mpeg", "mp4", "m4a", "aac", "ogg"})


def _play_file_with_default_app(path: str) -> None:
	"""Open an audio file using the platform default application."""
	try:
		if sys.platform == "win32":
			os.startfile(path)  # type: ignore[attr-defined]
		elif sys.platform == "darwin":
			subprocess.run(["open", path], check=False)
		else:
			subprocess.run(["xdg-open", path], check=False)
	except Exception as exc:
		log.error(
			"Failed to open audio with default app: %s", exc, exc_info=True
		)


def play_audio_from_base64(data: str, format: str = "wav") -> None:
	"""Decode base64 audio, write to temp file, and play.

	Args:
		data: Base64-encoded audio bytes.
		format: Audio format (wav, mp3, etc). WAV is played in-app; MP3 and
			other common formats are opened with the OS default player (e.g. Lyria).
	"""
	if not data:
		return
	fmt = format.lower().lstrip(".")
	try:
		raw = base64.b64decode(data)
		suffix = f".{fmt}" if fmt else ".wav"
		with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
			tmp.write(raw)
			path = tmp.name
		# End looping progress sound. OpenAI WAV goes through play_sound(), which
		# calls stop_sound internally; Lyria MP3 uses the OS player and never did.
		stop_sound()
		if fmt in _WAV:
			play_sound(path)
		elif fmt in _EXTERNAL or fmt in {"audio", "x-m4a"}:
			_play_file_with_default_app(path)
		else:
			log.debug(
				"Audio format %s not supported for in-app playback; trying OS handler",
				format,
			)
			_play_file_with_default_app(path)
		# Note: temp file is not deleted immediately since playback may be async.
	except Exception as exc:
		log.error("Failed to play audio: %s", exc, exc_info=True)
