"""Top-level tuning kwargs that chat HTTP/SDK engines pass in one dict.

These names are the only keys ``strip_disallowed_completion_dict_params``
(in :mod:`basilisk.model_catalog.sampling`) may remove when catalog metadata
disallows them. Structural fields (``model``, ``messages``, ``stream``,
``input``, ``tools``, …) must not appear here.

Engines that build such a dict set ``BaseEngine.catalog_strip_candidate_keys``
to this set (or to a provider-specific superset).
"""

from __future__ import annotations

CHAT_CLIENT_TUNING_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
	{
		"temperature",
		"top_p",
		"max_tokens",
		"max_completion_tokens",
		"frequency_penalty",
		"presence_penalty",
		"seed",
		"stop",
		"n",
		"logit_bias",
		"logprobs",
		"top_logprobs",
		"response_format",
	}
)
