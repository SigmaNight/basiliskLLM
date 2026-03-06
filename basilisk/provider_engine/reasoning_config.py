"""Provider-specific reasoning configuration.

Maps UI to exact API parameters per provider. No arbitrary values or compromises.
"""

# Effort/level options per provider. Values are exact API strings.
# xAI: only "low" and "high" (API does not support "medium")
# OpenAI, Gemini 3: "low", "medium", "high"
EFFORT_OPTIONS_XAI = ("low", "high")
EFFORT_OPTIONS_OPENAI_GEMINI3 = ("low", "medium", "high")


def get_effort_options(provider_id: str, model_id: str = "") -> tuple[str, ...]:
	"""Return effort options for the provider. Values match API exactly."""
	model_id = (model_id or "").lower()
	if provider_id == "xai":
		return EFFORT_OPTIONS_XAI
	if provider_id == "google" and "gemini-3" in model_id:
		return EFFORT_OPTIONS_OPENAI_GEMINI3
	if provider_id == "openai":
		return EFFORT_OPTIONS_OPENAI_GEMINI3
	return EFFORT_OPTIONS_OPENAI_GEMINI3


def get_effort_label(provider_id: str, model_id: str = "") -> str:
	"""Return provider-specific label for effort/level control."""
	model_id = (model_id or "").lower()
	if provider_id == "google" and "gemini-3" in model_id:
		# Gemini API uses "thinking_level"
		return "Thinking level:"
	# OpenAI: "reasoning.effort", xAI: "reasoning_effort"
	return "Reasoning effort:"
