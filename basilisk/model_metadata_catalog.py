"""SigmaNight/model-metadata catalog URLs and source labels.

All engines that load model lists from
https://github.com/SigmaNight/model-metadata ``data/*.json`` should use
:func:`sigma_night_data_file` so URLs and sampling/UI policy stay aligned.

OpenRouter uses the OpenRouter HTTP API for discovery; those models are tagged
with :data:`CATALOG_SOURCE_OPENROUTER_API` (not SigmaNight master JSON).
"""

from __future__ import annotations

SIGMA_NIGHT_MASTER_DATA_BASE = (
	"https://raw.githubusercontent.com/SigmaNight/model-metadata/master/data"
)

# Stored on ``ProviderAIModel.extra_info`` (see ``ModelExtraInfoKey``).
METADATA_CATALOG_EXTRA_KEY = "metadata_catalog"
CATALOG_SOURCE_SIGMA_NIGHT_MASTER = "sigma_night/master"
CATALOG_SOURCE_OPENROUTER_API = "openrouter/api"


def sigma_night_data_file(filename: str) -> str:
	"""Return the raw GitHub URL for ``data/{filename}``.

	Args:
		filename: File under ``data/`` (e.g. ``openai.json``).

	Returns:
		HTTPS URL suitable for :func:`load_models_from_url`.
	"""
	name = filename.lstrip("/").removeprefix("data/")
	return f"{SIGMA_NIGHT_MASTER_DATA_BASE}/{name}"


OPENAI_MODEL_METADATA_URL = sigma_night_data_file("openai.json")
ANTHROPIC_MODEL_METADATA_URL = sigma_night_data_file("anthropic.json")
MISTRAL_MODEL_METADATA_URL = sigma_night_data_file("mistralai.json")
GOOGLE_MODEL_METADATA_URL = sigma_night_data_file("google.json")
XAI_MODEL_METADATA_URL = sigma_night_data_file("x-ai.json")
DEEPSEEK_MODEL_METADATA_URL = sigma_night_data_file("deepseek.json")

SIGMA_NIGHT_MODEL_LIST_URLS: frozenset[str] = frozenset(
	{
		OPENAI_MODEL_METADATA_URL,
		ANTHROPIC_MODEL_METADATA_URL,
		MISTRAL_MODEL_METADATA_URL,
		GOOGLE_MODEL_METADATA_URL,
		XAI_MODEL_METADATA_URL,
		DEEPSEEK_MODEL_METADATA_URL,
	}
)
