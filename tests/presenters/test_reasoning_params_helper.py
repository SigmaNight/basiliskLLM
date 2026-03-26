"""Tests for reasoning_params_helper."""

from unittest.mock import MagicMock

from basilisk.presenters.reasoning_params_helper import (
	get_audio_params_from_view,
	get_reasoning_params_from_view,
)


class TestGetReasoningParamsFromView:
	"""Tests for get_reasoning_params_from_view."""

	def test_returns_defaults_when_no_reasoning_mode_widget(self):
		"""When view has no reasoning_mode, returns default dict."""
		view = MagicMock(spec=[])
		result = get_reasoning_params_from_view(view)
		assert result == {
			"reasoning_mode": False,
			"reasoning_budget_tokens": None,
			"reasoning_effort": None,
			"reasoning_adaptive": False,
		}

	def test_returns_defaults_when_reasoning_mode_not_shown(self):
		"""When reasoning_mode.IsShown() is False, returns defaults."""
		view = MagicMock()
		view.reasoning_mode = MagicMock()
		view.reasoning_mode.IsShown.return_value = False
		result = get_reasoning_params_from_view(view)
		assert result["reasoning_mode"] is False

	def test_extracts_reasoning_mode_true(self):
		"""When reasoning_mode.GetValue() is True, sets reasoning_mode."""
		view = MagicMock()
		view.reasoning_mode = MagicMock()
		view.reasoning_mode.IsShown.return_value = True
		view.reasoning_mode.GetValue.return_value = True
		view.reasoning_adaptive = MagicMock()
		view.reasoning_adaptive.GetValue.return_value = False
		result = get_reasoning_params_from_view(view)
		assert result["reasoning_mode"] is True

	def test_extracts_reasoning_budget_tokens(self):
		"""When reasoning_budget_spin present, extracts value."""
		view = MagicMock()
		view.reasoning_mode = MagicMock()
		view.reasoning_mode.IsShown.return_value = True
		view.reasoning_mode.GetValue.return_value = True
		view.reasoning_adaptive = MagicMock()
		view.reasoning_adaptive.GetValue.return_value = False
		view.reasoning_budget_spin = MagicMock()
		view.reasoning_budget_spin.GetValue.return_value = 8000
		result = get_reasoning_params_from_view(view)
		assert result["reasoning_budget_tokens"] == 8000


class TestGetAudioParamsFromView:
	"""Tests for get_audio_params_from_view."""

	def test_returns_defaults_when_no_output_modality_choice(self):
		"""When view has no output_modality_choice, returns text default."""
		view = MagicMock(spec=[])
		result = get_audio_params_from_view(view)
		assert result["output_modality"] == "text"
		assert result["audio_format"] == "wav"

	def test_audio_modality_when_selection_is_1(self):
		"""When output_modality_choice.GetSelection() is 1, output_modality is audio."""
		view = MagicMock()
		view.output_modality_choice = MagicMock()
		view.output_modality_choice.GetSelection.return_value = 1
		result = get_audio_params_from_view(view)
		assert result["output_modality"] == "audio"

	def test_text_modality_when_selection_is_0(self):
		"""When output_modality_choice.GetSelection() is 0, output_modality is text."""
		view = MagicMock()
		view.output_modality_choice = MagicMock()
		view.output_modality_choice.GetSelection.return_value = 0
		result = get_audio_params_from_view(view)
		assert result["output_modality"] == "text"
