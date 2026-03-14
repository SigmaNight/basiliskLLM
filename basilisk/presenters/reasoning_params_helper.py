"""Helper for extracting reasoning parameters from conversation views.

Shared logic used by ConversationPresenter, EditBlockPresenter, and
EditConversationProfilePresenter to avoid duplication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from basilisk.conversation.conversation_params import ReasoningParamKey
from basilisk.provider_engine.provider_ui_spec import DEFAULT_AUDIO_VOICES

if TYPE_CHECKING:
	from basilisk.provider_ai_model import ProviderAIModel
	from basilisk.provider_engine.base_engine import BaseEngine


def get_reasoning_params_from_view(
	view: Any,
	engine: BaseEngine | None = None,
	model: ProviderAIModel | None = None,
) -> dict[str, Any]:
	"""Extract reasoning params from view widgets for MessageBlock/ConversationProfile.

	Uses engine.get_reasoning_ui_spec(model) for effort options when available.

	Args:
		view: View with reasoning_mode, reasoning_adaptive, reasoning_budget_spin,
			reasoning_effort_choice widgets (or subset).
		engine: Engine for effort options (uses view.current_engine if not passed).
		model: Model for effort options (uses view.current_model if not passed).

	Returns:
		Dict with keys: reasoning_mode, reasoning_budget_tokens, reasoning_effort,
		reasoning_adaptive. Safe to pass as MessageBlock kwargs.
	"""
	result: dict[str, Any] = {
		ReasoningParamKey.REASONING_MODE: False,
		ReasoningParamKey.REASONING_BUDGET_TOKENS: None,
		ReasoningParamKey.REASONING_EFFORT: None,
		ReasoningParamKey.REASONING_ADAPTIVE: False,
	}
	if not hasattr(view, "reasoning_mode") or not view.reasoning_mode.IsShown():
		return result

	val = view.reasoning_mode.GetValue()
	result[ReasoningParamKey.REASONING_MODE] = (
		bool(val) if isinstance(val, bool) else False
	)

	if hasattr(view, "reasoning_adaptive"):
		val = view.reasoning_adaptive.GetValue()
		result[ReasoningParamKey.REASONING_ADAPTIVE] = (
			bool(val) if isinstance(val, bool) else False
		)

	if hasattr(view, "reasoning_budget_spin"):
		val = view.reasoning_budget_spin.GetValue()
		result[ReasoningParamKey.REASONING_BUDGET_TOKENS] = (
			val if isinstance(val, int) else None
		)

	if hasattr(view, "reasoning_effort_choice"):
		eng = engine or getattr(view, "current_engine", None)
		mod = model or getattr(view, "current_model", None)
		options = ()
		if eng and mod:
			spec = eng.get_reasoning_ui_spec(mod)
			opts = getattr(spec, "effort_options", ())
			if isinstance(opts, (tuple, list)) and all(
				isinstance(s, str) for s in opts
			):
				options = tuple(opts)
		if not options:
			result[ReasoningParamKey.REASONING_EFFORT] = None
		else:
			effort_idx = view.reasoning_effort_choice.GetSelection()
			effort_val = None
			if isinstance(effort_idx, int) and 0 <= effort_idx < len(options):
				effort_val = options[effort_idx]
			elif options:
				effort_val = options[-1]
			result[ReasoningParamKey.REASONING_EFFORT] = (
				effort_val if isinstance(effort_val, str) else None
			)

	return result


def get_audio_params_from_view(
	view: Any,
	engine: BaseEngine | None = None,
	model: ProviderAIModel | None = None,
) -> dict[str, Any]:
	"""Extract audio output params from view for MessageBlock/ConversationProfile.

	Uses engine.get_audio_output_spec(model) for voice list when available.

	Args:
		view: View with output_modality_choice, audio_voice_choice (or subset).
		engine: Engine for voice options (uses view.current_engine if not passed).
		model: Model for voice options (uses view.current_model if not passed).

	Returns:
		Dict with keys: output_modality, audio_voice, audio_format (always "wav").
	"""
	result: dict[str, Any] = {
		"output_modality": "text",
		"audio_voice": DEFAULT_AUDIO_VOICES[0]
		if DEFAULT_AUDIO_VOICES
		else "default",
		"audio_format": "wav",
	}
	if not hasattr(view, "output_modality_choice"):
		return result

	sel = view.output_modality_choice.GetSelection()
	result["output_modality"] = (
		"audio" if isinstance(sel, int) and sel == 1 else "text"
	)

	if hasattr(view, "audio_voice_choice"):
		eng = engine or getattr(view, "current_engine", None)
		mod = model or getattr(view, "current_model", None)
		voices = DEFAULT_AUDIO_VOICES
		if eng and mod:
			spec = eng.get_audio_output_spec(mod)
			if spec:
				voices = spec.voices
		idx = view.audio_voice_choice.GetSelection()
		if isinstance(idx, int) and 0 <= idx < len(voices):
			result["audio_voice"] = voices[idx]

	return result
