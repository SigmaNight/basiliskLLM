"""Tests for BaseEngine model caching behavior."""

from __future__ import annotations

from functools import cached_property
from types import SimpleNamespace
from unittest.mock import MagicMock

from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_engine.base_engine import BaseEngine


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


def test_models_cached_within_ttl(monkeypatch):
	"""Repeated access within TTL uses the same loaded list."""
	engine = _engine([[_model("one")]])
	monkeypatch.setattr(engine, "_get_models_cache_ttl_seconds", lambda: 60)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.monotonic", lambda: 100.0
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
		"basilisk.provider_engine.base_engine.time.monotonic",
		lambda: next(times),
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
		"basilisk.provider_engine.base_engine.time.monotonic",
		lambda: next(times),
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
		"basilisk.provider_engine.base_engine.time.monotonic", lambda: 100.0
	)
	assert engine.models == []
	assert engine.get_model_loading_error() == "network down"


def test_invalidate_models_cache_forces_reload(monkeypatch):
	"""Explicit invalidation clears cache so next call reloads models."""
	engine = _engine([[_model("first")], [_model("second")]])
	monkeypatch.setattr(engine, "_get_models_cache_ttl_seconds", lambda: 60)
	monkeypatch.setattr(
		"basilisk.provider_engine.base_engine.time.monotonic", lambda: 100.0
	)
	assert [m.id for m in engine.models] == ["first"]
	engine.invalidate_models_cache()
	assert [m.id for m in engine.models] == ["second"]
	assert engine.load_calls == 2
