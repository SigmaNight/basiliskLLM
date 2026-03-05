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
_CACHE_TTL_SECONDS = 3600


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


def _is_thinking_variant(model_id: str) -> bool:
	"""Return True if model id is a reasoning/thinking duplicate variant."""
	return ":thinking" in model_id or "_reasoning" in model_id


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


def _has_vision(modality: str | None) -> bool:
	"""Return True if modality indicates vision (image) support."""
	if not modality:
		return False
	return "image" in modality


def _has_reasoning_capable(supported: list[str] | None) -> bool:
	"""Return True if model supports optional reasoning via parameter."""
	if not supported:
		return False
	return "reasoning" in supported or "include_reasoning" in supported


def _get_created(model: dict[str, Any]) -> int:
	"""Extract created Unix timestamp, or 0 if absent."""
	val = model.get("created")
	if val is None:
		return 0
	try:
		return int(val)
	except TypeError, ValueError:
		return 0


def parse_model_metadata(raw: dict[str, Any]) -> list[ProviderAIModel]:
	"""Parse model-metadata JSON into ProviderAIModel list.

	Excludes :thinking and _reasoning variant entries (duplicates of base).
	Uses top_provider for context_length and max_completion_tokens.
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
		if _is_thinking_variant(model_id):
			continue

		supported = item.get("supported_parameters")
		if isinstance(supported, list):
			supported = [str(s) for s in supported]
		else:
			supported = []

		architecture = item.get("architecture") or {}
		modality = (
			architecture.get("modality")
			if isinstance(architecture, dict)
			else None
		)

		reasoning_capable = _has_reasoning_capable(supported)
		reasoning_only = False  # Provider-specific; set by engine if needed

		models.append(
			ProviderAIModel(
				id=model_id,
				name=item.get("name"),
				description=item.get("description"),
				context_window=_get_context_length(item),
				max_output_tokens=_get_max_completion_tokens(item),
				max_temperature=2.0,
				vision=_has_vision(modality),
				reasoning=reasoning_only,
				reasoning_capable=reasoning_capable,
				created=_get_created(item),
				supported_parameters=supported,
				extra_info={},
			)
		)

	models.sort(key=lambda m: m.created, reverse=True)
	return models


def load_models_from_url(url: str) -> list[ProviderAIModel]:
	"""Fetch and parse models from URL, with caching.

	Args:
		url: URL to model-metadata JSON.

	Returns:
		List of ProviderAIModel. Empty list on fetch/parse error.
	"""
	now = time.monotonic()
	if url in _CACHE:
		cached_models, cached_at = _CACHE[url]
		if now - cached_at < _CACHE_TTL_SECONDS:
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
