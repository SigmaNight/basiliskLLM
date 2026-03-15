"""Provider-injected UI specifications.

Engines define what settings they support via these dataclasses.
The view/presenter use them without knowing provider IDs.
"""

from __future__ import annotations

from dataclasses import dataclass

# Generic fallback when engine returns None for audio spec (model.audio True
# but no provider-specific voices). Avoid provider-specific defaults like "alloy".
DEFAULT_AUDIO_VOICES: tuple[str, ...] = ("default",)


@dataclass
class ReasoningUISpec:
	"""Descriptor for reasoning mode UI controls. Engine provides this.

	Each engine overrides get_reasoning_ui_spec() to return its spec.
	No provider IDs in presenter/view—engine is single source of truth.
	"""

	show: bool = False
	show_adaptive: bool = False
	show_budget: bool = False
	show_effort: bool = False
	effort_options: tuple[str, ...] = ()
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
	default_voice: str | None = None  # None = use first voice
