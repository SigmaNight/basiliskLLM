"""Tests for TokenUsage, ResponseTiming, and usage_utils."""

from datetime import datetime, timedelta

from basilisk.conversation.conversation_model import ResponseTiming, TokenUsage
from basilisk.provider_engine.usage_utils import (
	token_usage_anthropic,
	token_usage_gemini,
	token_usage_ollama,
	token_usage_openai_style,
	token_usage_responses_api,
)


class TestTokenUsage:
	"""Tests for TokenUsage model."""

	def test_effective_total_from_fields(self):
		"""effective_total uses input + output when total_tokens not set."""
		u = TokenUsage(input_tokens=10, output_tokens=5)
		assert u.effective_total == 15

	def test_effective_total_from_total_tokens(self):
		"""effective_total uses total_tokens when set."""
		u = TokenUsage(input_tokens=10, output_tokens=5, total_tokens=20)
		assert u.effective_total == 20

	def test_reasoning_tokens_optional(self):
		"""reasoning_tokens optional for non-reasoning models."""
		u = TokenUsage(input_tokens=1, output_tokens=2)
		assert u.reasoning_tokens is None


class TestResponseTiming:
	"""Tests for ResponseTiming model."""

	def test_duration_seconds(self):
		"""duration_seconds computes started_at to finished_at."""
		start = datetime(2026, 1, 1, 12, 0, 0)
		end = start + timedelta(seconds=5.5)
		t = ResponseTiming(started_at=start, finished_at=end)
		assert t.duration_seconds == 5.5

	def test_duration_seconds_none_when_incomplete(self):
		"""duration_seconds is None when started_at or finished_at missing."""
		assert ResponseTiming().duration_seconds is None
		assert (
			ResponseTiming(started_at=datetime.now()).duration_seconds is None
		)

	def test_time_to_first_token_seconds(self):
		"""time_to_first_token_seconds computes TTFT from request_sent to first_token."""
		req_sent = datetime(2026, 1, 1, 12, 0, 0)
		first = req_sent + timedelta(seconds=0.3)
		t = ResponseTiming(
			request_sent_at=req_sent,
			first_token_at=first,
			finished_at=first + timedelta(seconds=2),
		)
		assert t.time_to_first_token_seconds == 0.3

	def test_time_to_send_request_seconds(self):
		"""time_to_send_request_seconds is started_at to request_sent_at."""
		start = datetime(2026, 1, 1, 12, 0, 0)
		sent = start + timedelta(seconds=0.1)
		t = ResponseTiming(started_at=start, request_sent_at=sent)
		assert t.time_to_send_request_seconds == 0.1


class TestTokenUsageOpenaiStyle:
	"""Tests for token_usage_openai_style."""

	def test_from_object_with_attrs(self):
		"""Builds TokenUsage from object with prompt_tokens, completion_tokens."""
		u = type("Usage", (), {"prompt_tokens": 10, "completion_tokens": 5})()
		result = token_usage_openai_style(u)
		assert result.input_tokens == 10
		assert result.output_tokens == 5

	def test_from_dict(self):
		"""Builds TokenUsage from dict."""
		u = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
		result = token_usage_openai_style(u)
		assert result.input_tokens == 10
		assert result.output_tokens == 5
		assert result.total_tokens == 15


class TestTokenUsageAnthropic:
	"""Tests for token_usage_anthropic."""

	def test_basic_input_output(self):
		"""Builds TokenUsage from Anthropic input_tokens, output_tokens."""
		u = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
		result = token_usage_anthropic(u)
		assert result.input_tokens == 100
		assert result.output_tokens == 50

	def test_with_cache_creation_and_read(self):
		"""cached_input_tokens and cache_write_tokens mapped from Anthropic fields."""
		u = type(
			"Usage",
			(),
			{
				"input_tokens": 100,
				"output_tokens": 50,
				"cache_creation_input_tokens": 10,
				"cache_read_input_tokens": 20,
			},
		)()
		result = token_usage_anthropic(u)
		assert result.cached_input_tokens == 20
		assert result.cache_write_tokens == 10


class TestTokenUsageResponsesApi:
	"""Tests for token_usage_responses_api."""

	def test_with_reasoning_tokens(self):
		"""Extracts reasoning_tokens from output_token_details."""
		output_details = type("Details", (), {"reasoning_tokens": 100})()
		u = type(
			"Usage",
			(),
			{
				"input_tokens": 10,
				"output_tokens": 150,
				"output_token_details": output_details,
			},
		)()
		result = token_usage_responses_api(u)
		assert result.reasoning_tokens == 100
		assert result.output_tokens == 150


class TestTokenUsageGemini:
	"""Tests for token_usage_gemini."""

	def test_from_usage_metadata(self):
		"""Builds TokenUsage from Gemini usage_metadata."""
		um = type(
			"UsageMetadata",
			(),
			{
				"prompt_token_count": 10,
				"candidates_token_count": 5,
				"total_token_count": 15,
			},
		)()
		result = token_usage_gemini(um)
		assert result.input_tokens == 10
		assert result.output_tokens == 5
		assert result.total_tokens == 15


class TestTokenUsageOpenRouter:
	"""Tests for token_usage_openrouter."""

	def test_with_cost_cache_write_audio(self):
		"""Extracts cost, cache_write_tokens, audio_tokens from OpenRouter usage."""
		from basilisk.provider_engine.usage_utils import token_usage_openrouter

		details = {
			"cached_tokens": 50,
			"cache_write_tokens": 10,
			"audio_tokens": 5,
		}
		u = {
			"prompt_tokens": 200,
			"completion_tokens": 100,
			"total_tokens": 300,
			"prompt_tokens_details": details,
			"cost": 0.0123,
		}
		result = token_usage_openrouter(u)
		assert result.input_tokens == 200
		assert result.output_tokens == 100
		assert result.cached_input_tokens == 50
		assert result.cache_write_tokens == 10
		assert result.audio_tokens == 5
		assert result.cost == 0.0123


class TestTokenUsageOllama:
	"""Tests for token_usage_ollama."""

	def test_from_response_dict(self):
		"""Builds TokenUsage from Ollama response dict."""
		data = {"prompt_eval_count": 20, "eval_count": 30}
		result = token_usage_ollama(data)
		assert result.input_tokens == 20
		assert result.output_tokens == 30
