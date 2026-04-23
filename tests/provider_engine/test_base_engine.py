"""Tests for BaseEngine model caching behavior."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_engine.base_engine import BaseEngine
from basilisk.provider_engine.model_cache_registry import get_models_cache_dir


class DummyEngine(BaseEngine):
	"""Minimal engine for testing BaseEngine cache logic."""

	def __init__(self, account, loader_results):
		"""Initialize with deterministic model loader outputs."""
		super().__init__(account)
		self._loader_results = iter(loader_results)
		self.load_calls = 0

	@cached_property
	def client(self):
		"""Return a mock client object for abstract interface compliance."""
		return MagicMock()

	def _load_models(self) -> list[ProviderAIModel]:
		self.load_calls += 1
		result = next(self._loader_results)
		if isinstance(result, Exception):
			raise result
		return result

	def prepare_message_request(self, message):
		"""Echo request for abstract interface compliance."""
		return message

	def prepare_message_response(self, response):
		"""Echo response for abstract interface compliance."""
		return response

	def completion(self, new_block, conversation, system_message, **kwargs):
		"""Return placeholder completion for abstract interface compliance."""
		return None

	def completion_response_with_stream(self, stream, **kwargs):
		"""Echo stream for abstract interface compliance."""
		return stream

	def completion_response_without_stream(self, response, new_block, **kwargs):
		"""Echo new_block for abstract interface compliance."""
		return new_block


def _model(model_id: str) -> ProviderAIModel:
	return ProviderAIModel(id=model_id, name=model_id)


def _engine(loader_results) -> DummyEngine:
	account = SimpleNamespace(
		id="acct-1",
		custom_base_url=None,
		provider=SimpleNamespace(id="dummy-provider"),
	)
	return DummyEngine(account, loader_results)


@pytest.fixture(autouse=True)
def _isolated_models_cache_dir(tmp_path, monkeypatch):
	"""Ensure disk cache is isolated per test case."""
	monkeypatch.setattr(
		"basilisk.provider_engine.model_cache_registry.global_vars.user_data_path",
		tmp_path,
	)
	BaseEngine._last_cache_prune_at = 0.0
	DummyEngine._last_cache_prune_at = 0.0


def test_models_cached_within_ttl(monkeypatch):
	"""Repeated access within TTL uses the same loaded list."""
	engine = _engine([[_model("one")]])
	monkeypatch.setattr(engine, "_get_models_cache_ttl_seconds", lambda: 60)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: 100.0
	)
	assert [m.id for m in engine.models] == ["one"]
	assert [m.id for m in engine.models] == ["one"]
	assert engine.load_calls == 1


def test_models_reloaded_after_ttl_expires(monkeypatch):
	"""Expired TTL triggers a refresh on next access."""
	engine = _engine([[_model("old")], [_model("new")]])
	monkeypatch.setattr(engine, "_get_models_cache_ttl_seconds", lambda: 10)
	times = iter([100.0, 111.0])
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: next(times)
	)
	assert [m.id for m in engine.models] == ["old"]
	assert [m.id for m in engine.models] == ["new"]
	assert engine.load_calls == 2


def test_failed_refresh_returns_stale_cache(monkeypatch):
	"""When refresh fails, previously cached models are returned."""
	engine = _engine([[_model("cached")], RuntimeError("boom")])
	monkeypatch.setattr(engine, "_get_models_cache_ttl_seconds", lambda: 10)
	times = iter([100.0, 111.0])
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: next(times)
	)
	assert [m.id for m in engine.models] == ["cached"]
	assert [m.id for m in engine.models] == ["cached"]
	assert engine.get_model_loading_error() == "boom"
	assert engine.load_calls == 2


def test_failed_initial_load_returns_empty(monkeypatch):
	"""If there is no stale cache and loading fails, return empty list."""
	engine = _engine([RuntimeError("network down")])
	monkeypatch.setattr(engine, "_get_models_cache_ttl_seconds", lambda: 10)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: 100.0
	)
	assert engine.models == []
	assert engine.get_model_loading_error() == "network down"


def test_invalidate_models_cache_forces_reload(monkeypatch):
	"""Explicit invalidation clears cache so next call reloads models."""
	engine = _engine([[_model("first")], [_model("second")]])
	monkeypatch.setattr(engine, "_get_models_cache_ttl_seconds", lambda: 60)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: 100.0
	)
	assert [m.id for m in engine.models] == ["first"]
	engine.invalidate_models_cache()
	assert [m.id for m in engine.models] == ["second"]
	assert engine.load_calls == 2


def test_models_loaded_from_disk_cache_after_restart(tmp_path, monkeypatch):
	"""Fresh disk cache should be reusable by a new engine instance."""
	cache_file = tmp_path / "models-cache.json"
	engine = _engine([[_model("persisted")]])
	monkeypatch.setattr(engine, "_get_models_cache_ttl_seconds", lambda: 60)
	engine._models_cache_file_path = Path(cache_file)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: 100.0
	)
	assert [m.id for m in engine.models] == ["persisted"]
	assert engine.load_calls == 1

	restarted_engine = _engine([RuntimeError("must not reload")])
	monkeypatch.setattr(
		restarted_engine, "_get_models_cache_ttl_seconds", lambda: 60
	)
	restarted_engine._models_cache_file_path = Path(cache_file)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: 120.0
	)
	assert [m.id for m in restarted_engine.models] == ["persisted"]
	assert restarted_engine.load_calls == 0


def test_expired_disk_cache_reloads_models(tmp_path, monkeypatch):
	"""Expired disk cache should trigger a fresh load."""
	cache_file = tmp_path / "models-cache.json"
	seed_engine = _engine([[_model("stale")]])
	seed_engine._models_cache_file_path = Path(cache_file)
	monkeypatch.setattr(
		seed_engine, "_get_models_cache_ttl_seconds", lambda: 60
	)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: 100.0
	)
	assert [m.id for m in seed_engine.models] == ["stale"]

	restarted_engine = _engine([[_model("fresh")]])
	restarted_engine._models_cache_file_path = Path(cache_file)
	monkeypatch.setattr(
		restarted_engine, "_get_models_cache_ttl_seconds", lambda: 60
	)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: 200.0
	)
	assert [m.id for m in restarted_engine.models] == ["fresh"]
	assert restarted_engine.load_calls == 1


def test_cache_write_failure_does_not_break_successful_refresh(monkeypatch):
	"""Model refresh should still succeed when disk cache write fails."""
	engine = _engine([[_model("live")]])
	monkeypatch.setattr(engine, "_get_models_cache_ttl_seconds", lambda: 60)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: 100.0
	)

	def _raise_cache_write(*args, **kwargs):
		raise OSError("disk full")

	monkeypatch.setattr(engine, "_write_models_disk_cache", _raise_cache_write)
	assert [m.id for m in engine.models] == ["live"]
	assert engine.get_model_loading_error() is None


def test_unsupported_disk_cache_version_is_ignored(tmp_path, monkeypatch):
	"""Old cache payload versions should be ignored and rebuilt."""
	cache_file = tmp_path / "models-cache.json"
	cache_file.write_text(
		'{"version":999,"cached_at":100.0,"models":[{"id":"stale"}]}',
		encoding="utf-8",
	)
	engine = _engine([[_model("fresh")]])
	monkeypatch.setattr(engine, "_get_models_cache_ttl_seconds", lambda: 60)
	engine._models_cache_file_path = Path(cache_file)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: 120.0
	)
	assert [m.id for m in engine.models] == ["fresh"]
	assert engine.load_calls == 1


def test_too_old_stale_cache_is_removed_and_not_used(tmp_path, monkeypatch):
	"""Stale cache older than max stale window should be deleted."""
	cache_file = tmp_path / "models-cache.json"
	cache_file.write_text(
		'{"version":1,"cached_at":0.0,"models":[{"id":"ancient"}]}',
		encoding="utf-8",
	)
	engine = _engine([RuntimeError("network down")])
	engine._models_cache_file_path = Path(cache_file)
	monkeypatch.setattr(engine, "_get_models_cache_ttl_seconds", lambda: 10)
	monkeypatch.setattr(
		engine, "_get_models_cache_max_stale_seconds", lambda _ttl: 20
	)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.time", lambda: 100.0
	)
	assert engine.models == []
	assert not cache_file.exists()


def test_prune_removes_obsolete_cache_files(tmp_path, monkeypatch):
	"""Directory prune should remove invalid and expired cache files."""
	engine = _engine([[_model("live")]])
	cache_dir = get_models_cache_dir()
	cache_dir.mkdir(parents=True, exist_ok=True)
	(valid_file, old_file, bad_file) = (
		cache_dir / "valid.json",
		cache_dir / "old.json",
		cache_dir / "bad.json",
	)
	valid_file.write_text(
		'{"version":1,"cached_at":95.0,"models":[{"id":"ok"}]}',
		encoding="utf-8",
	)
	old_file.write_text(
		'{"version":1,"cached_at":1.0,"models":[{"id":"old"}]}',
		encoding="utf-8",
	)
	bad_file.write_text("not-json", encoding="utf-8")
	DummyEngine._last_cache_prune_at = 0.0
	monkeypatch.setattr(
		engine, "_get_models_cache_max_stale_seconds", lambda _ttl: 20
	)
	engine._prune_models_cache_dir(now=100.0, ttl_seconds=10)
	assert valid_file.exists()
	assert not old_file.exists()
	assert not bad_file.exists()
