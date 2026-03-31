"""Tests for generation parameter name StrEnums."""

from basilisk.provider_engine.generation_param import (
	FILTERABLE_GENERATION_PARAMS,
	FilterableGenerationParam,
)


def test_filterable_params_matches_enum_values():
	"""The exported frozenset is exactly the set of enum wire strings."""
	assert len(FILTERABLE_GENERATION_PARAMS) == len(FilterableGenerationParam)
	assert FILTERABLE_GENERATION_PARAMS == {
		p.value for p in FilterableGenerationParam
	}
