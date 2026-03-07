"""Unified audio layer for BasiliskLLM.

Provides a singleton AudioManager accessible via get_manager(),
and shortcut functions play() and stop().
"""

from __future__ import annotations

from typing import Optional

from .manager import AudioManager

_manager: Optional[AudioManager] = None


def initialize(
	input_device: Optional[int] = None, output_device: Optional[int] = None
) -> None:
	"""Initialise the global AudioManager singleton.

	Args:
		input_device: Default input device index, or None for system default.
		output_device: Default output device index, or None for system default.
	"""
	global _manager
	_manager = AudioManager(
		input_device=input_device, output_device=output_device
	)


def get_manager() -> AudioManager:
	"""Return the global AudioManager singleton.

	Returns:
		The initialised AudioManager instance.

	Raises:
		RuntimeError: If initialize() has not been called.
	"""
	if _manager is None:
		raise RuntimeError(
			"Audio manager not initialized. Call audio.initialize() first."
		)
	return _manager


def play(sound: str, loop: bool = False) -> None:
	"""Play a named sound using the global AudioManager.

	Args:
		sound: Sound alias or file path string.
		loop: Whether to loop the sound continuously.
	"""
	get_manager().play(sound, loop)


def stop() -> None:
	"""Stop the currently playing sound using the global AudioManager."""
	get_manager().stop()
