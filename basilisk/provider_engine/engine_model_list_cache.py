"""Disk-backed cache for provider model lists (dynamic catalog engines).

``BaseEngine`` coordinates RAM refresh and concurrency; this module owns the
on-disk JSON payload format, path derivation, atomic writes, directory prune,
and registry hooks shared with ``model_cache_registry``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import asdict
from pathlib import Path

from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_engine.model_cache_registry import (
	get_models_cache_dir,
	get_registry_filename,
	prune_model_cache_registry,
	register_model_cache_file,
	remove_cache_file_from_registry,
	write_json_atomic,
)

log = logging.getLogger(__name__)

MODEL_LIST_CACHE_PAYLOAD_VERSION = 1
PRUNE_INTERVAL_SECONDS = 3600
STALE_TTL_MULTIPLIER = 7

# Mutable throttle timestamp without a ``global`` statement.
_prune_last_at: list[float] = [0.0]
_prune_lock = threading.Lock()


def model_list_disk_cache_path(
	*,
	account_id: str,
	provider_id: str,
	custom_base_url: str | None,
	engine_cls_name: str,
	models_json_url: str | None,
) -> Path:
	"""Return the JSON cache file path for one account/engine/url tuple."""
	cache_key_payload = {
		"account_id": account_id,
		"provider_id": provider_id,
		"base_url": custom_base_url,
		"engine_cls": engine_cls_name,
		"models_json_url": models_json_url,
	}
	cache_key = hashlib.sha256(
		json.dumps(cache_key_payload, sort_keys=True).encode("utf-8")
	).hexdigest()
	cache_dir = get_models_cache_dir()
	return cache_dir / f"{cache_key}.json"


def delete_model_list_disk_cache_file(cache_file: Path) -> None:
	"""Delete one cache file, logging only on failure."""
	try:
		cache_file.unlink(missing_ok=True)
	except OSError:
		log.debug("Could not delete models cache file %s", cache_file)
	remove_cache_file_from_registry(cache_file.name)


def read_model_list_disk_cache(
	cache_file: Path,
	*,
	cache_kind_label: str,
	now: float,
	ttl_seconds: int,
	allow_stale: bool = False,
	max_stale_seconds: int | None = None,
) -> tuple[list[ProviderAIModel], float] | None:
	"""Read model cache payload from disk when valid for current TTL."""
	if not cache_file.exists():
		return None
	try:
		payload = json.loads(cache_file.read_text(encoding="utf-8"))
		if not isinstance(payload, dict):
			raise TypeError("invalid cache payload")
		if payload.get("version") != MODEL_LIST_CACHE_PAYLOAD_VERSION:
			raise ValueError("unsupported cache payload version")
		cached_at = float(payload["cached_at"])
		cache_age_seconds = now - cached_at
		if not allow_stale and cache_age_seconds >= ttl_seconds:
			log.debug(
				"Models disk cache expired for %s (age=%.1fs, ttl=%ss)",
				cache_kind_label,
				cache_age_seconds,
				ttl_seconds,
			)
			return None
		if (
			allow_stale
			and max_stale_seconds is not None
			and cache_age_seconds >= max_stale_seconds
		):
			log.debug(
				"Models stale disk cache exceeded retention for %s "
				"(age=%.1fs, max_stale=%ss)",
				cache_kind_label,
				cache_age_seconds,
				max_stale_seconds,
			)
			delete_model_list_disk_cache_file(cache_file)
			return None
		model_rows = payload.get("models")
		if not isinstance(model_rows, list):
			raise TypeError("invalid models cache payload")
		models = [ProviderAIModel(**x) for x in model_rows]
		return models, cached_at
	except (
		OSError,
		json.JSONDecodeError,
		KeyError,
		TypeError,
		ValueError,
	) as exc:
		log.warning("Failed reading models disk cache: %s", exc)
		delete_model_list_disk_cache_file(cache_file)
		return None


def write_model_list_disk_cache(
	cache_file: Path,
	account_id: str,
	models: list[ProviderAIModel],
	cached_at: float,
) -> None:
	"""Persist model cache payload to disk and register the file."""
	payload = {
		"version": MODEL_LIST_CACHE_PAYLOAD_VERSION,
		"cached_at": cached_at,
		"models": [asdict(model) for model in models],
	}
	write_json_atomic(cache_file, payload)
	register_model_cache_file(account_id, cache_file)


def prune_model_list_cache_dir(*, now: float, max_stale_seconds: int) -> None:
	"""Periodically remove obsolete cache files to limit file growth."""
	last_prune_at = _prune_last_at[0]
	if last_prune_at > 0 and now - last_prune_at < PRUNE_INTERVAL_SECONDS:
		return
	with _prune_lock:
		last_prune_at = _prune_last_at[0]
		if last_prune_at > 0 and now - last_prune_at < PRUNE_INTERVAL_SECONDS:
			return
		_prune_last_at[0] = now
	prune_model_cache_registry()
	cache_dir = get_models_cache_dir()
	if not cache_dir.exists():
		return
	for cache_file in cache_dir.glob("*.json"):
		if cache_file.name == get_registry_filename():
			continue
		try:
			payload = json.loads(cache_file.read_text(encoding="utf-8"))
			cached_at = float(payload["cached_at"])
			version = payload.get("version")
			if version != MODEL_LIST_CACHE_PAYLOAD_VERSION:
				delete_model_list_disk_cache_file(cache_file)
				continue
			if now - cached_at >= max_stale_seconds:
				delete_model_list_disk_cache_file(cache_file)
		except OSError, json.JSONDecodeError, KeyError, TypeError, ValueError:
			delete_model_list_disk_cache_file(cache_file)
