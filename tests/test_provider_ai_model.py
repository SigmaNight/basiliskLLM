"""Tests for ProviderAIModel and ModelMode."""

from __future__ import annotations

from basilisk.provider_ai_model import ModelMode, ProviderAIModel


class TestModelMode:
	"""Tests for ModelMode enum."""

	def test_values(self):
		"""Enum string values match expected strings."""
		assert ModelMode.TEXT == "text"
		assert ModelMode.VOICE == "voice"
		assert ModelMode.MULTIMODAL == "multimodal"

	def test_get_labels_covers_all_modes(self):
		"""get_labels() returns a mapping for every ModelMode member."""
		labels = ModelMode.get_labels()
		for mode in ModelMode:
			assert mode in labels

	def test_labels_are_non_empty_strings(self):
		"""All label values are non-empty strings."""
		for label in ModelMode.get_labels().values():
			assert isinstance(label, str)
			assert label


class TestProviderAIModelDefaults:
	"""Tests for ProviderAIModel default field values."""

	def test_default_mode_is_text(self):
		"""Mode defaults to ModelMode.TEXT."""
		model = ProviderAIModel(id="test-model")
		assert model.mode == ModelMode.TEXT

	def test_voice_mode(self):
		"""Explicit VOICE mode is stored."""
		model = ProviderAIModel(id="gpt-realtime", mode=ModelMode.VOICE)
		assert model.mode == ModelMode.VOICE

	def test_multimodal_mode(self):
		"""Explicit MULTIMODAL mode is stored."""
		model = ProviderAIModel(id="gemini-pro", mode=ModelMode.MULTIMODAL)
		assert model.mode == ModelMode.MULTIMODAL


class TestDisplayModel:
	"""Tests for ProviderAIModel.display_model property."""

	def test_returns_five_tuple(self):
		"""display_model returns a 5-element tuple."""
		model = ProviderAIModel(id="gpt-4", name="GPT-4", context_window=128000)
		result = model.display_model
		assert len(result) == 5

	def test_first_element_is_display_name(self):
		"""First element is the model's display name."""
		model = ProviderAIModel(id="gpt-4", name="GPT-4")
		assert model.display_model[0] == "GPT-4 (gpt-4)"

	def test_second_element_is_mode_label(self):
		"""Second element is the localised mode label."""
		model_text = ProviderAIModel(id="m1", mode=ModelMode.TEXT)
		model_voice = ProviderAIModel(id="m2", mode=ModelMode.VOICE)
		labels = ModelMode.get_labels()
		assert model_text.display_model[1] == labels[ModelMode.TEXT]
		assert model_voice.display_model[1] == labels[ModelMode.VOICE]

	def test_third_element_is_vision_support(self):
		"""Third element indicates vision support."""
		model_vision = ProviderAIModel(id="m1", vision=True)
		model_no_vision = ProviderAIModel(id="m2", vision=False)
		# The value is the translated string, which may differ; just check type
		assert isinstance(model_vision.display_model[2], str)
		assert isinstance(model_no_vision.display_model[2], str)
		assert model_vision.display_model[2] != model_no_vision.display_model[2]

	def test_fourth_element_is_context_window(self):
		"""Fourth element is context window as string."""
		model = ProviderAIModel(id="m1", context_window=8192)
		assert model.display_model[3] == "8192"

	def test_fifth_element_empty_when_non_positive_tokens(self):
		"""Fifth element is empty string when max_output_tokens <= 0."""
		model_zero = ProviderAIModel(id="m1", max_output_tokens=0)
		model_neg = ProviderAIModel(id="m2", max_output_tokens=-1)
		assert model_zero.display_model[4] == ""
		assert model_neg.display_model[4] == ""

	def test_fifth_element_non_empty_when_positive_tokens(self):
		"""Fifth element is the token count when max_output_tokens > 0."""
		model = ProviderAIModel(id="m1", max_output_tokens=4096)
		assert model.display_model[4] == "4096"


class TestDisplayDetails:
	"""Tests for ProviderAIModel.display_details property."""

	def test_includes_mode_label(self):
		"""display_details contains the mode label."""
		model = ProviderAIModel(id="m1", mode=ModelMode.VOICE)
		labels = ModelMode.get_labels()
		assert labels[ModelMode.VOICE] in model.display_details

	def test_includes_display_name(self):
		"""display_details starts with the display name."""
		model = ProviderAIModel(id="gpt-4", name="GPT-4")
		assert model.display_details.startswith("GPT-4 (gpt-4)")

	def test_includes_vision_info(self):
		"""display_details contains vision information."""
		model = ProviderAIModel(id="m1", vision=True)
		assert "Vision:" in model.display_details

	def test_includes_context_window(self):
		"""display_details contains context window information."""
		model = ProviderAIModel(id="m1", context_window=4096)
		assert "Context window:" in model.display_details
		assert "4096" in model.display_details

	def test_max_tokens_shown_only_when_positive(self):
		"""Max output tokens line appears only when > 0."""
		model_pos = ProviderAIModel(id="m1", max_output_tokens=2048)
		model_zero = ProviderAIModel(id="m2", max_output_tokens=0)
		assert "Max output tokens:" in model_pos.display_details
		assert "Max output tokens:" not in model_zero.display_details

	def test_includes_extra_info(self):
		"""Extra key-value pairs appear in display_details."""
		model = ProviderAIModel(
			id="m1", extra_info={"pricing": "$0.01/1k", "tier": "standard"}
		)
		assert "pricing: $0.01/1k" in model.display_details
		assert "tier: standard" in model.display_details
