"""Generic pricing utilities for model metadata JSON.

Supports OpenRouter-style pricing structure. Other providers can use the same
JSON format; when "pricing" is present it is parsed. When absent, pricing is None.

OpenRouter models API (https://openrouter.ai/api/v1/models) returns per-model:
  "pricing": {
    "prompt": "0.000008",        # USD per input token
    "completion": "0.000024",   # USD per output token
    "image": "0",                # USD per image
    "request": "0",              # USD per request
    "input_cache_read": "0"      # USD per cached input token
  }

Model-metadata JSON for other providers uses the same structure when pricing
is available. Values are strings to avoid floating-point precision issues.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
	from basilisk.conversation.conversation_model import (
		Conversation,
		MessageBlock,
	)
	from basilisk.provider_engine.base_engine import BaseEngine


@dataclass(frozen=True)
class ModelPricing:
	"""Per-token pricing in USD. All values are per-unit (token/image/request)."""

	prompt: float = 0.0  # input tokens
	completion: float = 0.0  # output tokens
	image: float = 0.0  # per image
	request: float = 0.0  # per request
	input_cache_read: float = 0.0  # cached input tokens
	input_cache_write: float = 0.0  # cache write tokens (different pricing)
	audio: float = 0.0  # audio input tokens

	def has_usable_pricing(self) -> bool:
		"""True if we can compute cost from token usage."""
		return (
			self.prompt > 0
			or self.completion > 0
			or self.input_cache_read > 0
			or self.input_cache_write > 0
			or self.audio > 0
		)

	def format_for_display(self) -> str:
		"""Human-readable pricing summary (OpenRouter-style)."""
		lines = []
		if self.prompt > 0:
			lines.append(f"  prompt: ${self.prompt * 1_000_000:.2f}/M tokens")
		if self.completion > 0:
			lines.append(
				f"  completion: ${self.completion * 1_000_000:.2f}/M tokens"
			)
		if self.input_cache_read > 0:
			lines.append(
				f"  input_cache_read: ${self.input_cache_read * 1_000_000:.2f}/M tokens"
			)
		if self.input_cache_write > 0:
			lines.append(
				f"  input_cache_write: ${self.input_cache_write * 1_000_000:.2f}/M tokens"
			)
		if self.audio > 0:
			lines.append(f"  audio: ${self.audio * 1_000_000:.2f}/M tokens")
		if self.image > 0:
			lines.append(f"  image: ${self.image * 1000:.3f}/K imgs")
		if self.request > 0:
			lines.append(f"  request: ${self.request}/request")
		return "\n".join(lines) if lines else ""


def parse_pricing_from_json(item: dict[str, Any]) -> ModelPricing | None:
	"""Parse pricing from model JSON (OpenRouter-style).

	Expects optional "pricing" key with dict of usage_type -> price string.
	Returns None if pricing is absent, empty, or invalid.

	Args:
		item: Model object from JSON (e.g. from data array).

	Returns:
		ModelPricing when valid pricing exists, else None.
	"""
	pricing = item.get("pricing")
	if not isinstance(pricing, dict):
		return None

	def _to_float(val: Any) -> float:
		if val is None or val == "0":
			return 0.0
		try:
			return float(Decimal(str(val)))
		except TypeError, ValueError:
			return 0.0

	prompt = _to_float(pricing.get("prompt"))
	completion = _to_float(pricing.get("completion"))
	image = _to_float(pricing.get("image"))
	request = _to_float(pricing.get("request"))
	input_cache_read = _to_float(pricing.get("input_cache_read"))
	input_cache_write = _to_float(pricing.get("input_cache_write"))
	audio = _to_float(pricing.get("audio"))

	# If all zero, treat as no pricing
	if not (
		prompt
		or completion
		or image
		or request
		or input_cache_read
		or input_cache_write
		or audio
	):
		return None

	return ModelPricing(
		prompt=prompt,
		completion=completion,
		image=image,
		request=request,
		input_cache_read=input_cache_read,
		input_cache_write=input_cache_write,
		audio=audio,
	)


def compute_cost_from_usage(
	pricing: ModelPricing,
	input_tokens: int,
	output_tokens: int,
	cached_input_tokens: int | None = None,
	reasoning_tokens: int | None = None,
	cache_write_tokens: int | None = None,
	audio_tokens: int | None = None,
	image_count: int = 0,
) -> float:
	"""Compute estimated cost from token usage and model pricing.

	Uses prompt/completion/input_cache_read/input_cache_write/audio.
	Reasoning tokens use completion price. Cached tokens use input_cache_read
	when available, else prompt.

	Args:
		pricing: Model pricing.
		input_tokens: Total input tokens.
		output_tokens: Total output tokens.
		cached_input_tokens: Cached portion of input (uses input_cache_read).
		reasoning_tokens: Reasoning portion of output (uses completion price).
		cache_write_tokens: Tokens written to cache (uses input_cache_write).
		audio_tokens: Audio input tokens (uses audio price).
		image_count: Number of images.

	Returns:
		Estimated cost in USD.
	"""
	cached = cached_input_tokens or 0
	cache_write = cache_write_tokens or 0
	audio = audio_tokens or 0
	# Fresh input = total input minus cached, cache_write, audio (they're separate)
	fresh_input = max(0, input_tokens - cached - cache_write - audio)
	input_cost = fresh_input * pricing.prompt
	input_cost += cached * (
		pricing.input_cache_read
		if pricing.input_cache_read > 0
		else pricing.prompt
	)
	input_cost += cache_write * (
		pricing.input_cache_write
		if pricing.input_cache_write > 0
		else pricing.prompt
	)
	input_cost += audio * (
		pricing.audio if pricing.audio > 0 else pricing.prompt
	)
	output_cost = output_tokens * pricing.completion
	image_cost = image_count * pricing.image
	return input_cost + output_cost + image_cost + pricing.request


def _add_cost(
	result: dict[str, float], key: str, amount: float, price: float
) -> None:
	"""Add cost entry if amount and price are positive."""
	if amount > 0 and price > 0:
		result[key] = amount * price


def compute_cost_breakdown(
	pricing: ModelPricing,
	input_tokens: int,
	output_tokens: int,
	cached_input_tokens: int | None = None,
	reasoning_tokens: int | None = None,
	cache_write_tokens: int | None = None,
	audio_tokens: int | None = None,
	image_count: int = 0,
) -> dict[str, float]:
	"""Compute cost breakdown by token type for display.

	Returns a dict with keys: input, output, reasoning, cached, cache_write,
	audio, image, request. Only non-zero entries are included.
	"""
	cached = cached_input_tokens or 0
	cache_write = cache_write_tokens or 0
	audio = audio_tokens or 0
	fresh_input = max(0, input_tokens - cached - cache_write - audio)

	result: dict[str, float] = {}
	_add_cost(result, "input", fresh_input, pricing.prompt)

	if output_tokens > 0 and pricing.completion > 0:
		reasoning = reasoning_tokens or 0
		text_output = max(0, output_tokens - reasoning)
		_add_cost(result, "output", text_output, pricing.completion)
		_add_cost(result, "reasoning", reasoning, pricing.completion)

	cached_price = (
		pricing.input_cache_read
		if pricing.input_cache_read > 0
		else pricing.prompt
	)
	_add_cost(result, "cached", cached, cached_price)

	cache_write_price = (
		pricing.input_cache_write
		if pricing.input_cache_write > 0
		else pricing.prompt
	)
	_add_cost(result, "cache_write", cache_write, cache_write_price)

	audio_price = pricing.audio if pricing.audio > 0 else pricing.prompt
	_add_cost(result, "audio", audio, audio_price)

	_add_cost(result, "image", float(image_count), pricing.image)
	if pricing.request > 0:
		result["request"] = pricing.request
	return result


def get_price_at(
	history: dict[str, dict[str, float]], block_created_at_iso: str
) -> dict[str, float]:
	"""Get effective pricing at a given datetime from history.

	History format: field -> ISO datetime -> price. Uses the largest key <=
	block_created_at_iso.

	Args:
		history: Per-field pricing history (e.g. prompt, completion).
		block_created_at_iso: Block created_at as ISO string (UTC).

	Returns:
		Dict of field -> price for that point in time.
	"""
	result: dict[str, float] = {}
	for field, timestamps in history.items():
		if not isinstance(timestamps, dict):
			continue
		valid = [k for k in timestamps if k <= block_created_at_iso]
		if not valid:
			continue
		best = max(valid)
		val = timestamps.get(best)
		if isinstance(val, (int, float)):
			result[field] = float(val)
	return result


def merge_pricing_into_conversation(
	conversation: "Conversation",
	model_id: str,
	pricing: ModelPricing,
	at_iso: str,
) -> None:
	"""Merge current model pricing into conversation's pricing_snapshot.

	Updates conversation.pricing_snapshot in place. Uses ISO datetime keys.

	Args:
		conversation: Conversation to update.
		model_id: Model identifier (e.g. anthropic/claude-sonnet-4).
		pricing: Current model pricing.
		at_iso: ISO datetime string (UTC) for this snapshot.
	"""
	if model_id not in conversation.pricing_snapshot:
		conversation.pricing_snapshot[model_id] = {}

	fields = {
		"prompt": pricing.prompt,
		"completion": pricing.completion,
		"input_cache_read": pricing.input_cache_read,
		"input_cache_write": pricing.input_cache_write,
		"audio": pricing.audio,
		"image": pricing.image,
		"request": pricing.request,
	}
	for field, price in fields.items():
		if price <= 0:
			continue
		if field not in conversation.pricing_snapshot[model_id]:
			conversation.pricing_snapshot[model_id][field] = {}
		conversation.pricing_snapshot[model_id][field][at_iso] = price


def apply_block_cost_and_pricing(
	block: "MessageBlock", conversation: "Conversation", engine: "BaseEngine"
) -> None:
	"""Set block.cost and merge pricing into conversation after completion.

	Called from completion_handler after streaming/non-streaming finish.
	Uses usage.cost if provider reports it; otherwise computes from pricing.
	Merges model pricing into conversation.pricing_snapshot for history.

	Args:
		block: The completed message block (with usage set).
		conversation: The conversation to update.
		engine: The engine used (for get_model).
	"""
	model_id = f"{block.model.provider_id}/{block.model.model_id}"
	model = engine.get_model(block.model.model_id)
	usage = block.usage

	# Cost: prefer provider-reported, else compute from pricing
	if usage and usage.cost is not None:
		block.cost = usage.cost
		# Compute breakdown when we have pricing (for display)
		if model and model.pricing and model.pricing.has_usable_pricing():
			block.cost_breakdown = compute_cost_breakdown(
				model.pricing,
				usage.input_tokens,
				usage.output_tokens,
				cached_input_tokens=usage.cached_input_tokens,
				reasoning_tokens=usage.reasoning_tokens,
				cache_write_tokens=usage.cache_write_tokens,
				audio_tokens=usage.audio_tokens,
			)
	elif (
		usage and model and model.pricing and model.pricing.has_usable_pricing()
	):
		block.cost = compute_cost_from_usage(
			model.pricing,
			usage.input_tokens,
			usage.output_tokens,
			cached_input_tokens=usage.cached_input_tokens,
			reasoning_tokens=usage.reasoning_tokens,
			cache_write_tokens=usage.cache_write_tokens,
			audio_tokens=usage.audio_tokens,
		)
		block.cost_breakdown = compute_cost_breakdown(
			model.pricing,
			usage.input_tokens,
			usage.output_tokens,
			cached_input_tokens=usage.cached_input_tokens,
			reasoning_tokens=usage.reasoning_tokens,
			cache_write_tokens=usage.cache_write_tokens,
			audio_tokens=usage.audio_tokens,
		)

	# Merge pricing into conversation snapshot (ISO datetime keys)
	if model and model.pricing and model.pricing.has_usable_pricing():
		at_iso = block.created_at.isoformat()
		merge_pricing_into_conversation(
			conversation, model_id, model.pricing, at_iso
		)
