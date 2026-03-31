"""Tests for shared config enums."""

from basilisk.config import (
	ACCOUNT_MODEL_SORT_KEYS,
	MODEL_SORT_KEYS,
	AccountModelSortKeyEnum,
	ModelSortKeyEnum,
)


def test_model_sort_keys_tuple_matches_enum():
	"""Exported tuple stays aligned with ModelSortKeyEnum order."""
	assert tuple(m.value for m in ModelSortKeyEnum) == MODEL_SORT_KEYS


def test_account_model_sort_keys_tuple_matches_enum():
	"""Exported tuple stays aligned with AccountModelSortKeyEnum order."""
	assert (
		tuple(m.value for m in AccountModelSortKeyEnum)
		== ACCOUNT_MODEL_SORT_KEYS
	)
