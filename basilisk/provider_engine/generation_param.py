"""Generation / sampling parameter names shared by engines and model metadata."""

from __future__ import annotations

import enum


class FilterableGenerationParam(enum.StrEnum):
	"""Params that may be omitted when absent from ``model.supported_parameters``."""

	TEMPERATURE = "temperature"
	TOP_P = "top_p"
	MAX_TOKENS = "max_tokens"
	FREQUENCY_PENALTY = "frequency_penalty"
	PRESENCE_PENALTY = "presence_penalty"
	SEED = "seed"
	TOP_K = "top_k"
	STOP = "stop"
	REASONING = "reasoning"
	AUDIO = "audio"
	WEB_SEARCH_MODE = "web_search_mode"


FILTERABLE_GENERATION_PARAMS: frozenset[str] = frozenset(
	FilterableGenerationParam
)
