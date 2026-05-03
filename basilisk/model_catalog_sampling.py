"""Catalog-driven sampling limits for API requests and main UI.

Maps ``supported_parameters`` / ``unsupported_parameters`` from model-metadata
into allow/deny decisions shared by engines and conversation views.

Models loaded from SigmaNight ``data/*.json`` URLs are tagged in
``extra_info[metadata_catalog]`` (see :mod:`basilisk.model_metadata_catalog`);
OpenRouter API rows use a separate tag so policy stays explicit per source.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

SUPPORTED_PARAMETERS_EXTRA_KEY = "supported_parameters"
UNSUPPORTED_PARAMETERS_EXTRA_KEY = "unsupported_parameters"

_MAX_TOKEN_PARAM_ALIASES: frozenset[str] = frozenset(
	{"max_tokens", "max_completion_tokens", "max_output_tokens"}
)

MAIN_UI_SAMPLING_PARAM_KEYS: tuple[str, ...] = (
	"max_tokens",
	"temperature",
	"top_p",
)


def _normalized_str_set(raw: Any) -> frozenset[str] | None:
	if not isinstance(raw, list) or not raw:
		return None
	out = {
		str(x).strip().lower() for x in raw if x is not None and str(x).strip()
	}
	return frozenset(out) if out else None


def _metadata_supported_set(model: Any) -> frozenset[str] | None:
	if model is None:
		return None
	ex = getattr(model, "extra_info", None)
	if not isinstance(ex, dict):
		return None
	return _normalized_str_set(ex.get(SUPPORTED_PARAMETERS_EXTRA_KEY))


def _metadata_unsupported_set(model: Any) -> frozenset[str]:
	if model is None:
		return frozenset()
	ex = getattr(model, "extra_info", None)
	if not isinstance(ex, dict):
		return frozenset()
	raw = ex.get(UNSUPPORTED_PARAMETERS_EXTRA_KEY)
	if not isinstance(raw, list):
		return frozenset()
	return frozenset(
		str(x).strip().lower() for x in raw if x is not None and str(x).strip()
	)


def model_allows_api_sampling_param(model: Any, api_param_name: str) -> bool:
	"""Whether catalog metadata allows sending this sampling-related API field.

	``unsupported_parameters`` in ``extra_info`` rejects by name.
	When ``supported_parameters`` is non-empty, only listed names pass
	(plus max-token family aliases). Missing or empty metadata allows all.
	"""
	if model is None:
		return True
	name = api_param_name.strip().lower()
	if name in _metadata_unsupported_set(model):
		return False
	supported = _metadata_supported_set(model)
	if supported is None:
		return True
	if name in supported:
		return True
	if name in _MAX_TOKEN_PARAM_ALIASES:
		return bool(supported & _MAX_TOKEN_PARAM_ALIASES)
	return False


def sampling_visibility_for_main_ui(model: Any) -> dict[str, bool]:
	"""Return visibility flags for main-tab sampling rows (aligned key order)."""
	return {
		k: model_allows_api_sampling_param(model, k)
		for k in MAIN_UI_SAMPLING_PARAM_KEYS
	}


def strip_disallowed_completion_dict_params(
	model: Any, params: dict[str, Any], *, regulated_keys: frozenset[str]
) -> None:
	"""Drop top-level keys rejected by model metadata (in place).

	Only keys present in ``regulated_keys`` are considered (callers pass the
	set their engine puts in the client request dict, so structural fields
	are never removed).

	Args:
		model: Catalog model; may be None if metadata is unknown.
		params: Client request kwargs.
		regulated_keys: Candidate top-level names the catalog may veto.
	"""
	if model is None:
		return
	keys = regulated_keys
	model_id = getattr(model, "id", "?")
	for key in list(params):
		if key not in keys:
			continue
		if model_allows_api_sampling_param(model, key):
			continue
		params.pop(key, None)
		log.debug(
			"Omitted completion param %r for model %s (catalog metadata)",
			key,
			model_id,
		)
