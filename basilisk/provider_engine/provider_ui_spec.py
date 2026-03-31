"""Provider-injected UI specifications."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_AUDIO_VOICES: tuple[str, ...] = ("default",)


@dataclass
class ReasoningUISpec:
	"""Descriptor for reasoning mode UI controls."""

	show: bool = False
	show_adaptive: bool = False
	show_budget: bool = False
	show_effort: bool = False
	effort_options: tuple[str, ...] = ()
	# Translators: Label shown next to the reasoning effort meter
	effort_label: str = "Reasoning effort:"
	budget_default: int = 16000
	budget_max: int = 128000


@dataclass
class AudioOutputUISpec:
	"""Descriptor for audio output controls. Engine provides this.

	When model supports audio output (TTS), engine returns voices and default.
	Use default_voice=None to mean "first voice in list".
	"""

	voices: tuple[str, ...]
	default_voice: str | None = None
