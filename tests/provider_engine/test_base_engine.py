"""Tests for BaseEngine param filtering."""

from unittest.mock import MagicMock

import pytest

from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_engine.base_engine import BaseEngine


class _ConcreteEngine(BaseEngine):
	"""Minimal concrete engine for testing _filter_params_for_model."""

	client = property(lambda self: MagicMock())
	models = property(lambda self: [])

	def prepare_message_request(self, message):
		pass

	def prepare_message_response(self, response):
		pass

	def completion(self, *args, **kwargs):
		pass

	def completion_response_with_stream(self, *args, **kwargs):
		pass

	def completion_response_without_stream(self, *args, **kwargs):
		pass


@pytest.fixture
def engine():
	"""Return a concrete engine for testing."""
	return _ConcreteEngine(account=MagicMock())


def test_filter_params_includes_supported(engine):
	"""Params in supported_parameters are included."""
	model = ProviderAIModel(
		id="test", supported_parameters=["temperature", "max_tokens"]
	)
	params = {
		"model": "test",
		"temperature": 0.7,
		"max_tokens": 1000,
		"top_p": 1.0,
	}
	result = engine._filter_params_for_model(model, params)
	assert result["temperature"] == 0.7
	assert result["max_tokens"] == 1000
	assert result["model"] == "test"
	assert "top_p" not in result


def test_filter_params_excludes_unsupported(engine):
	"""Params not in supported_parameters are excluded (for filterable keys)."""
	model = ProviderAIModel(id="test", supported_parameters=["temperature"])
	params = {
		"model": "test",
		"temperature": 0.7,
		"top_p": 1.0,
		"frequency_penalty": 0.5,
	}
	result = engine._filter_params_for_model(model, params)
	assert result["temperature"] == 0.7
	assert result["model"] == "test"
	assert "top_p" not in result
	assert "frequency_penalty" not in result


def test_filter_params_empty_list_passthrough(engine):
	"""When supported_parameters is empty, all params pass through."""
	model = ProviderAIModel(id="test", supported_parameters=[])
	params = {"model": "test", "temperature": 0.7, "top_p": 1.0}
	result = engine._filter_params_for_model(model, params)
	assert result == params


def test_get_reasoning_ui_spec_hidden_when_not_capable(engine):
	"""Reasoning spec shows=False when model is not reasoning_capable."""
	model = ProviderAIModel(id="test", reasoning_capable=False, reasoning=False)
	spec = engine.get_reasoning_ui_spec(model)
	assert spec.show is False


def test_get_reasoning_ui_spec_hidden_when_reasoning_only(engine):
	"""Reasoning spec shows=False when model is reasoning-only (always on)."""
	model = ProviderAIModel(id="test", reasoning_capable=True, reasoning=True)
	spec = engine.get_reasoning_ui_spec(model)
	assert spec.show is False


def test_get_reasoning_ui_spec_show_when_capable(engine):
	"""Reasoning spec shows=True when model is reasoning_capable and not reasoning."""
	model = ProviderAIModel(id="test", reasoning_capable=True, reasoning=False)
	spec = engine.get_reasoning_ui_spec(model)
	assert spec.show is True
	assert spec.effort_options == ()


def test_get_audio_output_spec_returns_none_by_default(engine):
	"""Base engine returns None for audio output spec."""
	model = ProviderAIModel(id="test", audio=True)
	assert engine.get_audio_output_spec(model) is None


def test_get_model_returns_match(mocker):
	"""get_model returns the sole model with the given id."""
	only = ProviderAIModel(id="mid")
	mocker.patch.object(
		_ConcreteEngine,
		"models",
		new_callable=lambda: property(lambda self: [only]),
	)
	eng = _ConcreteEngine(account=MagicMock())
	assert eng.get_model("mid") is only


def test_get_model_none_when_missing(mocker):
	"""get_model returns None when id is not in the list."""
	mocker.patch.object(
		_ConcreteEngine,
		"models",
		new_callable=lambda: property(
			lambda self: [ProviderAIModel(id="other")]
		),
	)
	eng = _ConcreteEngine(account=MagicMock())
	assert eng.get_model("missing") is None


def test_get_model_raises_on_duplicate_ids(mocker):
	"""get_model raises when more than one model shares the same id."""
	a = ProviderAIModel(id="dup")
	b = ProviderAIModel(id="dup")
	mocker.patch.object(
		_ConcreteEngine,
		"models",
		new_callable=lambda: property(lambda self: [a, b]),
	)
	eng = _ConcreteEngine(account=MagicMock())
	with pytest.raises(ValueError, match="Multiple models"):
		eng.get_model("dup")
