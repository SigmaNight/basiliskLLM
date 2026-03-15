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


def _get_float(obj: Any, attr: str) -> float | None:
	"""Get float attribute or dict key. Returns None if missing or invalid."""
	if hasattr(obj, attr):
		val = getattr(obj, attr, None)
		if val is not None:
			try:
				return float(val)
			except TypeError, ValueError:
				pass
	if isinstance(obj, dict) and attr in obj:
		val = obj.get(attr)
		if val is not None:
			try:
				return float(val)
			except TypeError, ValueError:
				pass
	return None


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
	"""Build TokenUsage from Anthropic usage (input_tokens, output_tokens, cache fields).

	Anthropic: cache_read_input_tokens -> cached_input_tokens,
	cache_creation_input_tokens -> cache_write_tokens.
	"""
	cached = _get(u, "cache_read_input_tokens", None)
	cache_write = _get(u, "cache_creation_input_tokens", None)
	return TokenUsage(
		input_tokens=_get(u, "input_tokens", 0) or 0,
		output_tokens=_get(u, "output_tokens", 0) or 0,
		cached_input_tokens=cached,
		cache_write_tokens=cache_write,
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


def token_usage_openrouter(u: Any) -> TokenUsage:
	"""Build TokenUsage from OpenRouter usage.

	OpenRouter uses OpenAI-style prompt_tokens/completion_tokens/total_tokens,
	plus optional prompt_tokens_details (cached_tokens, cache_write_tokens,
	audio_tokens), completion_tokens_details.reasoning_tokens, and usage.cost.
	"""
	cached = None
	cache_write = None
	audio = None
	details = getattr(u, "prompt_tokens_details", None) or (
		u.get("prompt_tokens_details") if isinstance(u, dict) else None
	)
	if details:
		cached = _get(details, "cached_tokens")
		cache_write = _get(details, "cache_write_tokens", None)
		audio = _get(details, "audio_tokens", None)
	reasoning = None
	comp_details = getattr(u, "completion_tokens_details", None) or (
		u.get("completion_tokens_details") if isinstance(u, dict) else None
	)
	if comp_details:
		reasoning = _get(comp_details, "reasoning_tokens")
	cost = _get_float(u, "cost")
	return TokenUsage(
		input_tokens=_get(u, "prompt_tokens", 0) or 0,
		output_tokens=_get(u, "completion_tokens", 0) or 0,
		total_tokens=_get(u, "total_tokens"),
		cached_input_tokens=cached,
		cache_write_tokens=cache_write,
		audio_tokens=audio,
		reasoning_tokens=reasoning,
		cost=cost,
	)


def token_usage_ollama(data: dict[str, Any]) -> TokenUsage:
	"""Build TokenUsage from Ollama response dict (prompt_eval_count, eval_count)."""
	return TokenUsage(
		input_tokens=data.get("prompt_eval_count") or 0,
		output_tokens=data.get("eval_count") or 0,
	)
