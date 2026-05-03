"""Tests for catalog-driven sampling policy (API + main UI)."""

from __future__ import annotations

import pytest

from basilisk.model_catalog_sampling import (
	MAIN_UI_SAMPLING_PARAM_KEYS,
	model_allows_api_sampling_param,
	sampling_visibility_for_main_ui,
	strip_disallowed_completion_dict_params,
)
from basilisk.provider_ai_model import ProviderAIModel


@pytest.mark.parametrize(
	("supported", "param", "expected"),
	[
		(None, "top_p", True),
		(["max_tokens", "temperature"], "top_p", False),
		(["max_tokens", "temperature", "top_p"], "top_p", True),
		(["max_completion_tokens"], "max_tokens", True),
	],
)
def test_model_allows_api_sampling_param_whitelist(
	supported: list[str] | None, param: str, expected: bool
) -> None:
	"""``supported_parameters`` gates sampling fields when non-empty."""
	ex: dict = {}
	if supported is not None:
		ex["supported_parameters"] = supported
	model = ProviderAIModel(id="m", extra_info=ex)
	assert model_allows_api_sampling_param(model, param) is expected


def test_model_allows_unsupported_overrides_supported() -> None:
	"""Explicit ``unsupported_parameters`` rejects even if also listed as supported."""
	model = ProviderAIModel(
		id="m",
		extra_info={
			"supported_parameters": ["temperature", "top_p"],
			"unsupported_parameters": ["top_p"],
		},
	)
	assert model_allows_api_sampling_param(model, "top_p") is False


def test_strip_disallowed_completion_dict_params_removes_top_p() -> None:
	"""``strip_disallowed_completion_dict_params`` drops keys not in metadata."""
	model = ProviderAIModel(
		id="gpt-test",
		extra_info={"supported_parameters": ["max_tokens", "temperature"]},
	)
	params = {
		"model": "gpt-test",
		"messages": [],
		"temperature": 0.5,
		"top_p": 0.9,
	}
	strip_disallowed_completion_dict_params(model, params)
	assert params["temperature"] == 0.5
	assert "top_p" not in params
	assert params["model"] == "gpt-test"


def test_strip_skips_when_model_none() -> None:
	"""Without catalog metadata, no keys are removed."""
	params = {"temperature": 1.0, "top_p": 1.0}
	strip_disallowed_completion_dict_params(None, params)
	assert params["top_p"] == 1.0


def test_sampling_visibility_for_main_ui_matches_key_order() -> None:
	"""Visibility map keys follow ``MAIN_UI_SAMPLING_PARAM_KEYS`` order."""
	model = ProviderAIModel(
		id="x",
		extra_info={"supported_parameters": ["max_tokens", "temperature"]},
	)
	vis = sampling_visibility_for_main_ui(model)
	assert tuple(vis.keys()) == MAIN_UI_SAMPLING_PARAM_KEYS
	assert vis["max_tokens"] is True
	assert vis["temperature"] is True
	assert vis["top_p"] is False
