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
