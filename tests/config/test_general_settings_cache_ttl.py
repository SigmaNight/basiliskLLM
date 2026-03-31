"""Tests for GeneralSettings model metadata cache TTL."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from basilisk.config.main_config import GeneralSettings


def test_model_metadata_cache_ttl_default():
	"""Default matches previous seven-hour window."""
	assert GeneralSettings().model_metadata_cache_ttl == timedelta(hours=7)


def test_numeric_seconds_in_cache_ttl_field():
	"""YAML/JSON may store duration as a number (Pydantic: seconds)."""
	g = GeneralSettings.model_validate({"model_metadata_cache_ttl": 3600})
	assert g.model_metadata_cache_ttl == timedelta(hours=1)


def test_string_iso8601_duration():
	"""Pydantic accepts ISO 8601 duration strings for timedelta fields."""
	g = GeneralSettings.model_validate({"model_metadata_cache_ttl": "P2D"})
	assert g.model_metadata_cache_ttl == timedelta(days=2)
	g = GeneralSettings.model_validate({"model_metadata_cache_ttl": "PT48H"})
	assert g.model_metadata_cache_ttl == timedelta(days=2)


def test_string_hms_duration_native_pydantic():
	"""HH:MM:SS strings are coerced by Pydantic; value floors to whole hours."""
	g = GeneralSettings.model_validate({"model_metadata_cache_ttl": "12:30:45"})
	assert g.model_metadata_cache_ttl == timedelta(hours=12)


def test_quoted_numeric_string_not_valid_timedelta():
	"""Quoted digits are strings: Pydantic does not treat them as seconds."""
	with pytest.raises(ValidationError):
		GeneralSettings.model_validate({"model_metadata_cache_ttl": "3600"})


def test_invalid_duration_string_raises():
	"""Invalid strings fail Pydantic timedelta parsing."""
	with pytest.raises(ValidationError):
		GeneralSettings.model_validate(
			{"model_metadata_cache_ttl": "not-a-time"}
		)
	with pytest.raises(ValidationError):
		GeneralSettings.model_validate({"model_metadata_cache_ttl": "1:00:99"})


def test_sub_hour_fraction_normalized_to_whole_hours():
	"""Non-integer-hour durations floor to whole hours after bounds check."""
	g = GeneralSettings.model_validate({"model_metadata_cache_ttl": 5400})
	assert g.model_metadata_cache_ttl == timedelta(hours=1)


def test_hour_constants_match_field_bounds():
	"""Public hour limits match timedelta min/max used by ``Field``."""
	from basilisk.config import (
		MODEL_METADATA_CACHE_TTL_HOURS_MAX,
		MODEL_METADATA_CACHE_TTL_HOURS_MIN,
	)

	assert MODEL_METADATA_CACHE_TTL_HOURS_MIN == 1
	assert MODEL_METADATA_CACHE_TTL_HOURS_MAX == 7 * 24


def test_direct_ttl_below_minimum_raises():
	"""Canonical field uses Pydantic bounds like other GeneralSettings numbers."""
	with pytest.raises(ValidationError):
		GeneralSettings.model_validate({"model_metadata_cache_ttl": 30})


def test_direct_ttl_above_maximum_raises():
	"""Oversized canonical TTL seconds fail validation (strict bounds)."""
	with pytest.raises(ValidationError):
		GeneralSettings.model_validate({"model_metadata_cache_ttl": 99999999})
