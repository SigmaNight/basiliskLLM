"""Helpers for persistent model-cache file registry management."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from platformdirs import user_cache_path

import basilisk.global_vars as global_vars
from basilisk.consts import APP_AUTHOR, APP_NAME

log = logging.getLogger(__name__)

_MODEL_CACHE_REGISTRY_VERSION = 1
_MODEL_CACHE_REGISTRY_FILENAME = "index.json"
_REGISTRY_LOCK = threading.Lock()


def get_cache_root_path() -> Path:
	"""Return root directory used for persisted cache files."""
	if global_vars.user_data_path:
		cache_root = global_vars.user_data_path / "cache"
		cache_root.mkdir(parents=True, exist_ok=True)
		return cache_root
	return user_cache_path(APP_NAME, APP_AUTHOR, ensure_exists=True)


def get_models_cache_dir() -> Path:
	"""Return the directory containing per-engine model cache files."""
	cache_dir = get_cache_root_path() / "models"
	cache_dir.mkdir(parents=True, exist_ok=True)
	return cache_dir


def _get_registry_file_path() -> Path:
	"""Return registry file path for model cache index."""
	return get_models_cache_dir() / _MODEL_CACHE_REGISTRY_FILENAME


def get_registry_filename() -> str:
	"""Return the model cache registry filename."""
	return _MODEL_CACHE_REGISTRY_FILENAME


def _write_text_atomic(path: Path, content: str) -> None:
	"""Write text atomically to avoid partial-file corruption."""
	temp_path = path.with_suffix(f"{path.suffix}.tmp")
	temp_path.write_text(content, encoding="utf-8")
	temp_path.replace(path)


def write_json_atomic(path: Path, payload: dict | list) -> None:
	"""Write JSON payload atomically with Basilisk formatting defaults."""
	_write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _load_registry_unlocked() -> dict:
	"""Load registry payload from disk, returning a normalized structure."""
	registry_file = _get_registry_file_path()
	if not registry_file.exists():
		return {"version": _MODEL_CACHE_REGISTRY_VERSION, "accounts": {}}
	try:
		payload = json.loads(registry_file.read_text(encoding="utf-8"))
		if not isinstance(payload, dict):
			raise TypeError("invalid registry payload")
		if payload.get("version") != _MODEL_CACHE_REGISTRY_VERSION:
			raise ValueError("unsupported registry version")
		accounts = payload.get("accounts")
		if not isinstance(accounts, dict):
			raise TypeError("invalid accounts mapping in registry")
		normalized_accounts: dict[str, list[str]] = {}
		for account_id, cache_files in accounts.items():
			if not isinstance(account_id, str):
				continue
			if not isinstance(cache_files, list):
				continue
			valid_files = sorted(
				{
					_normalize_cache_name(x)
					for x in cache_files
					if isinstance(x, str)
				}
			)
			if valid_files:
				normalized_accounts[account_id] = valid_files
		return {
			"version": _MODEL_CACHE_REGISTRY_VERSION,
			"accounts": normalized_accounts,
		}
	except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
		log.warning("Failed to read model cache registry: %s", exc)
		try:
			registry_file.unlink(missing_ok=True)
		except OSError:
			log.debug("Could not delete invalid model cache registry file")
		return {"version": _MODEL_CACHE_REGISTRY_VERSION, "accounts": {}}


def _save_registry_unlocked(payload: dict) -> None:
	"""Persist normalized registry payload to disk."""
	registry_file = _get_registry_file_path()
	write_json_atomic(registry_file, payload)


def _normalize_cache_name(cache_name: str) -> str:
	"""Normalize a cache filename to a basename."""
	return Path(cache_name).name


def _add_cache_name_unlocked(account_id: str, cache_name: str) -> None:
	"""Add one cache filename to an account."""
	payload = _load_registry_unlocked()
	accounts = payload["accounts"]
	files = set(accounts.get(account_id, []))
	files.add(cache_name)
	updated = sorted(files)
	if accounts.get(account_id) == updated:
		return
	accounts[account_id] = updated
	_save_registry_unlocked(payload)


def register_model_cache_file(account_id: str, cache_file: Path) -> None:
	"""Register a cache file for an account in the index."""
	cache_name = _normalize_cache_name(cache_file.name)
	with _REGISTRY_LOCK:
		_add_cache_name_unlocked(account_id, cache_name)


def remove_cache_file_from_registry(cache_name: str) -> None:
	"""Remove one cache filename from every account registry entry."""
	cache_name = _normalize_cache_name(cache_name)
	with _REGISTRY_LOCK:
		payload = _load_registry_unlocked()
		accounts = payload["accounts"]
		did_change = False
		for account_id in list(accounts):
			files = set(accounts[account_id])
			files.discard(cache_name)
			updated_files = sorted(files)
			if accounts.get(account_id) == updated_files:
				continue
			if files:
				accounts[account_id] = updated_files
			else:
				accounts.pop(account_id, None)
			did_change = True
		if did_change:
			_save_registry_unlocked(payload)


def remove_account_model_cache(account_id: str) -> None:
	"""Delete all indexed model cache files for one account."""
	with _REGISTRY_LOCK:
		payload = _load_registry_unlocked()
		accounts = payload["accounts"]
		cache_names = accounts.pop(account_id, [])
		if not cache_names:
			return
		cache_dir = get_models_cache_dir()
		for cache_name in cache_names:
			cache_file = cache_dir / _normalize_cache_name(cache_name)
			try:
				cache_file.unlink(missing_ok=True)
			except OSError:
				log.debug("Could not delete model cache file %s", cache_file)
		_save_registry_unlocked(payload)


def prune_model_cache_registry() -> None:
	"""Drop registry references to cache files that no longer exist."""
	with _REGISTRY_LOCK:
		payload = _load_registry_unlocked()
		accounts = payload["accounts"]
		cache_dir = get_models_cache_dir()
		did_change = False
		for account_id in list(accounts):
			normalized = [
				_normalize_cache_name(cache_name)
				for cache_name in accounts[account_id]
				if (cache_dir / _normalize_cache_name(cache_name)).exists()
			]
			existing = sorted(set(normalized))
			if accounts.get(account_id) == existing:
				continue
			if existing:
				accounts[account_id] = existing
			else:
				accounts.pop(account_id, None)
			did_change = True
		if did_change:
			_save_registry_unlocked(payload)
