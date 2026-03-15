"""Module for loading model metadata from JSON URLs.

Provides reusable fetch and parse logic for providers that use the
model-metadata JSON format (OpenAI, Anthropic, xAI, Mistral, etc.).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from basilisk.consts import APP_NAME, APP_SOURCE_URL
from basilisk.provider_ai_model import ProviderAIModel

log = logging.getLogger(__name__)

_CACHE: dict[str, tuple[list[ProviderAIModel], float]] = {}


def _get_user_agent() -> str:
	"""Return user agent for HTTP requests."""
	return f"{APP_NAME} ({APP_SOURCE_URL})"


def fetch_models_json(url: str) -> dict[str, Any]:
	"""Fetch model metadata JSON from URL.

	Args:
		url: URL to fetch (e.g. model-metadata JSON).

	Returns:
		Parsed JSON dict with "data" key containing model list.

	Raises:
		httpx.HTTPError: On request failure.
	"""
	response = httpx.get(
		url, headers={"User-Agent": _get_user_agent()}, timeout=30.0
	)
	response.raise_for_status()
	return response.json()


def _get_max_completion_tokens(model: dict[str, Any]) -> int:
	"""Extract max_completion_tokens from top_provider, or -1 if absent."""
	top = model.get("top_provider")
	if not top or not isinstance(top, dict):
		return -1
	val = top.get("max_completion_tokens")
	if val is None:
		return -1
	try:
		return int(val)
	except TypeError, ValueError:
		return -1


def _get_context_length(model: dict[str, Any]) -> int:
	"""Extract context_length, preferring top_provider over root."""
	top = model.get("top_provider")
	if top and isinstance(top, dict) and top.get("context_length") is not None:
		try:
			return int(top["context_length"])
		except TypeError, ValueError:
			pass
	val = model.get("context_length")
	if val is None:
		return 0
	try:
		return int(val)
	except TypeError, ValueError:
		return 0


def _modality_flags(architecture: dict[str, Any]) -> dict[str, bool]:
	"""Extract modality flags from architecture. Extensible for new modalities.

	Args:
		architecture: JSON architecture dict with modality, input_modalities,
			output_modalities.

	Returns:
		Dict with vision, audio, document, image_output booleans.
	"""
	modality = (architecture.get("modality") or "").lower()
	input_mods = architecture.get("input_modalities") or []
	if isinstance(input_mods, list):
		input_mods = [str(m).lower() for m in input_mods]
	else:
		input_mods = []
	output_mods = architecture.get("output_modalities") or []
	if isinstance(output_mods, list):
		output_mods = [str(m).lower() for m in output_mods]
	else:
		output_mods = []
	return {
		"vision": "image" in modality or "image" in input_mods,
		"audio": "audio" in modality or "audio" in input_mods,
		"document": "file" in modality or "file" in input_mods,
		"image_output": "image" in output_mods,
		"audio_output": "audio" in output_mods,
	}


def _has_reasoning_capable(supported: list[str] | None) -> bool:
	"""Return True if model supports optional reasoning via parameter."""
	if not supported:
		return False
	return "reasoning" in supported or "include_reasoning" in supported


def _has_web_search_capable(item: dict[str, Any], supported: list[str]) -> bool:
	"""Return True if model supports web search.

	Uses JSON supports_web_search if present; else fallback to "tools" in
	supported_parameters. Engines can override via model_supports_web_search.
	"""
	explicit = item.get("supports_web_search")
	if explicit is True:
		return True
	if explicit is False:
		return False
	return "tools" in supported


def _get_created(model: dict[str, Any]) -> int:
	"""Extract created Unix timestamp, or 0 if absent."""
	val = model.get("created")
	if val is None:
		return 0
	try:
		return int(val)
	except TypeError, ValueError:
		return 0


def _get_default_params(item: dict[str, Any]) -> dict[str, Any]:
	"""Extract default_parameters from JSON. Returns dict of param -> value.

	Values can be None (use API default), or a number/string. Used to set
	UI defaults and omit params when equal to model default.
	"""
	defaults = item.get("default_parameters")
	if not isinstance(defaults, dict):
		return {}
	return {str(k): v for k, v in defaults.items() if v is not None}


def parse_model_metadata(raw: dict[str, Any]) -> list[ProviderAIModel]:
	"""Parse model-metadata JSON into ProviderAIModel list.

	Uses JSON supported_parameters for reasoning_capable; top_provider for
	context_length and max_completion_tokens. No ID-based filtering—each
	engine handles provider-specific logic in _postprocess_models.
	Sorts by created descending (newest first) for UI display.

	Args:
		raw: JSON dict with "data" key containing model objects.

	Returns:
		List of ProviderAIModel instances, sorted by created desc.
	"""
	models: list[ProviderAIModel] = []
	data = raw.get("data")
	if not isinstance(data, list):
		return models

	for item in data:
		if not isinstance(item, dict):
			continue
		model_id = item.get("id")
		if not model_id or not isinstance(model_id, str):
			continue

		supported = item.get("supported_parameters")
		if isinstance(supported, list):
			supported = [str(s) for s in supported]
		else:
			supported = []

		architecture = item.get("architecture") or {}
		if not isinstance(architecture, dict):
			architecture = {}
		modalities = _modality_flags(architecture)

		reasoning_capable = _has_reasoning_capable(supported)
		# reasoning_only: set by each engine in _postprocess_models (OpenAI o3,
		# xAI grok-4, etc.). Loader stays generic—no provider-specific logic.
		web_search_capable = _has_web_search_capable(item, supported)
		default_params = _get_default_params(item)
		def_temp = default_params.get("temperature")
		default_temperature = float(def_temp) if def_temp is not None else 1.0

		models.append(
			ProviderAIModel(
				id=model_id,
				name=item.get("name"),
				description=item.get("description"),
				context_window=_get_context_length(item),
				max_output_tokens=_get_max_completion_tokens(item),
				max_temperature=2.0,
				default_temperature=default_temperature,
				vision=modalities["vision"],
				audio=modalities["audio"],
				document=modalities["document"],
				image_output=modalities.get("image_output", False),
				audio_output=modalities.get("audio_output", False),
				reasoning=False,
				reasoning_capable=reasoning_capable,
				web_search_capable=web_search_capable,
				created=_get_created(item),
				supported_parameters=supported,
				extra_info={"default_parameters": default_params},
			)
		)

	models.sort(key=lambda m: m.created, reverse=True)
	return models


def _get_cache_ttl_seconds() -> int:
	"""Return cache TTL from config. Deferred import to avoid circular deps."""
	import basilisk.config as config

	return config.conf().general.model_metadata_cache_ttl_seconds


def load_models_from_url(url: str) -> list[ProviderAIModel]:
	"""Fetch and parse models from URL, with caching.

	Args:
		url: URL to model-metadata JSON.

	Returns:
		List of ProviderAIModel. Empty list on fetch/parse error.
	"""
	now = time.monotonic()
	ttl = _get_cache_ttl_seconds()
	if url in _CACHE:
		cached_models, cached_at = _CACHE[url]
		if now - cached_at < ttl:
			return cached_models

	try:
		raw = fetch_models_json(url)
		models = parse_model_metadata(raw)
		_CACHE[url] = (models, now)
		log.debug("Loaded %d models from %s", len(models), url)
		return models
	except Exception as e:
		log.warning("Failed to load models from %s: %s", url, e)
		if url in _CACHE:
			return _CACHE[url][0]
		return []
