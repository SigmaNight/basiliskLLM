"""Utilities for extracting token usage from provider responses.

Normalizes provider-specific usage objects into TokenUsage.
"""

from __future__ import annotations

from typing import Any

from basilisk.conversation.conversation_model import TokenUsage


def _get(obj: Any, attr: str, default: int | None = 0) -> int | None:
	"""Get attribute or dict key, return default if missing or None."""
	if hasattr(obj, attr):
		val = getattr(obj, attr, None)
		if val is not None:
			return int(val)
	if isinstance(obj, dict) and attr in obj:
		val = obj.get(attr)
		if val is not None:
			return int(val)
	return default if default is not None else None


def token_usage_openai_style(
	u: Any,
	input_attr: str = "prompt_tokens",
	output_attr: str = "completion_tokens",
	total_attr: str = "total_tokens",
) -> TokenUsage:
	"""Build TokenUsage from OpenAI-style usage (prompt_tokens, completion_tokens)."""
	return TokenUsage(
		input_tokens=_get(u, input_attr, 0) or 0,
		output_tokens=_get(u, output_attr, 0) or 0,
		total_tokens=_get(u, total_attr),
	)


def token_usage_anthropic(u: Any) -> TokenUsage:
	"""Build TokenUsage from Anthropic usage (input_tokens, output_tokens, cache fields)."""
	cached = None
	if hasattr(u, "cache_creation_input_tokens") and hasattr(
		u, "cache_read_input_tokens"
	):
		c1, c2 = (
			_get(u, "cache_creation_input_tokens"),
			_get(u, "cache_read_input_tokens"),
		)
		if c1 is not None or c2 is not None:
			cached = (c1 or 0) + (c2 or 0)
	elif hasattr(u, "cache_read_input_tokens"):
		cached = _get(u, "cache_read_input_tokens")
	return TokenUsage(
		input_tokens=_get(u, "input_tokens", 0) or 0,
		output_tokens=_get(u, "output_tokens", 0) or 0,
		cached_input_tokens=cached,
	)


def token_usage_responses_api(u: Any) -> TokenUsage:
	"""Build TokenUsage from OpenAI Responses API usage (with token details)."""
	reasoning = None
	if hasattr(u, "output_token_details") and u.output_token_details:
		reasoning = _get(u.output_token_details, "reasoning_tokens")
	cached = None
	if hasattr(u, "input_token_details") and u.input_token_details:
		cached = _get(u.input_token_details, "cached_tokens")
	return TokenUsage(
		input_tokens=_get(u, "input_tokens", 0) or 0,
		output_tokens=_get(u, "output_tokens", 0) or 0,
		reasoning_tokens=reasoning,
		cached_input_tokens=cached,
		total_tokens=_get(u, "total_tokens"),
	)


def token_usage_gemini(um: Any) -> TokenUsage:
	"""Build TokenUsage from Gemini usage_metadata."""
	return TokenUsage(
		input_tokens=_get(um, "prompt_token_count", 0) or 0,
		output_tokens=_get(um, "candidates_token_count", 0) or 0,
		reasoning_tokens=_get(um, "thoughts_token_count"),
		cached_input_tokens=_get(um, "cached_content_token_count"),
		total_tokens=_get(um, "total_token_count"),
	)


def token_usage_ollama(data: dict[str, Any]) -> TokenUsage:
	"""Build TokenUsage from Ollama response dict (prompt_eval_count, eval_count)."""
	return TokenUsage(
		input_tokens=data.get("prompt_eval_count") or 0,
		output_tokens=data.get("eval_count") or 0,
	)
