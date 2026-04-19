"""Tests for model cache registry helpers."""

from pathlib import Path

from basilisk.provider_engine.model_cache_registry import (
	get_models_cache_dir,
	prune_model_cache_registry,
	register_model_cache_file,
	remove_account_model_cache,
	remove_cache_file_from_registry,
)


def _read_index(tmp_path: Path) -> str:
	index_path = tmp_path / "cache" / "models" / "index.json"
	if not index_path.exists():
		return ""
	return index_path.read_text(encoding="utf-8")


def test_register_and_remove_cache_file(monkeypatch, tmp_path):
	"""Registering then removing should update index content."""
	monkeypatch.setattr(
		"basilisk.provider_engine.model_cache_registry.global_vars.user_data_path",
		tmp_path,
	)
	cache_file = get_models_cache_dir() / "abc.json"
	cache_file.write_text("{}", encoding="utf-8")
	register_model_cache_file("acct-1", cache_file)
	assert "acct-1" in _read_index(tmp_path)
	remove_cache_file_from_registry(cache_file.name)
	assert "acct-1" not in _read_index(tmp_path)


def test_remove_account_model_cache_deletes_files(monkeypatch, tmp_path):
	"""Removing account cache should delete indexed files and keep others."""
	monkeypatch.setattr(
		"basilisk.provider_engine.model_cache_registry.global_vars.user_data_path",
		tmp_path,
	)
	cache_dir = get_models_cache_dir()
	keep_file = cache_dir / "keep.json"
	remove_file = cache_dir / "remove.json"
	keep_file.write_text("{}", encoding="utf-8")
	remove_file.write_text("{}", encoding="utf-8")
	register_model_cache_file("acct-1", remove_file)
	register_model_cache_file("acct-2", keep_file)
	remove_account_model_cache("acct-1")
	assert not remove_file.exists()
	assert keep_file.exists()
	index_content = _read_index(tmp_path)
	assert "acct-1" not in index_content
	assert "acct-2" in index_content


def test_prune_model_cache_registry_removes_missing_references(
	monkeypatch, tmp_path
):
	"""Prune should drop references to missing files."""
	monkeypatch.setattr(
		"basilisk.provider_engine.model_cache_registry.global_vars.user_data_path",
		tmp_path,
	)
	cache_dir = get_models_cache_dir()
	existing_file = cache_dir / "exists.json"
	missing_file = cache_dir / "missing.json"
	existing_file.write_text("{}", encoding="utf-8")
	register_model_cache_file("acct-1", existing_file)
	register_model_cache_file("acct-1", missing_file)
	prune_model_cache_registry()
	index_content = _read_index(tmp_path)
	assert "exists.json" in index_content
	assert "missing.json" not in index_content


def test_remove_cache_file_from_registry_removes_file_for_all_accounts(
	monkeypatch, tmp_path
):
	"""Single cache filename should be removed from all account entries."""
	monkeypatch.setattr(
		"basilisk.provider_engine.model_cache_registry.global_vars.user_data_path",
		tmp_path,
	)
	cache_dir = get_models_cache_dir()
	shared = cache_dir / "shared.json"
	shared.write_text("{}", encoding="utf-8")
	register_model_cache_file("acct-1", shared)
	register_model_cache_file("acct-2", shared)
	remove_cache_file_from_registry("shared.json")
	index_content = _read_index(tmp_path)
	assert "acct-1" not in index_content
	assert "acct-2" not in index_content
