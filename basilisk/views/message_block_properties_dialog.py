"""Dialog for displaying message block properties (request, response, usage, timing)."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

import wx

from basilisk.conversation.conversation_model import MessageBlock

from .sectioned_properties_dialog import (
	SectionedPropertiesDialog,
	format_datetime,
	section_header,
)


def _get_request_labels() -> dict[str, str]:
	"""Field name -> display label. Add new MessageBlock fields for automatic display."""
	return {
		"model": _("Model"),
		"temperature": _("Temperature"),
		"max_tokens": _("Max tokens"),
		"top_p": _("Top P"),
		"top_k": _("Top K"),
		"seed": _("Seed"),
		"stop": _("Stop"),
		"frequency_penalty": _("Frequency penalty"),
		"presence_penalty": _("Presence penalty"),
		"stream": _("Stream"),
		"reasoning_mode": _("Reasoning mode"),
		"reasoning_adaptive": _("Adaptive reasoning"),
		"reasoning_budget_tokens": _("Reasoning budget (tokens)"),
		"reasoning_effort": _("Reasoning effort"),
		"web_search_mode": _("Web search mode"),
		"output_modality": _("Output modality"),
		"audio_voice": _("Audio voice"),
		"audio_format": _("Audio format"),
		"system_index": _("System index"),
		"created_at": _("Created at"),
		"updated_at": _("Updated at"),
	}


def _get_usage_labels() -> dict[str, str]:
	return {
		"input_tokens": _("Input tokens"),
		"output_tokens": _("Output tokens"),
		"reasoning_tokens": _("Reasoning tokens"),
		"cached_input_tokens": _("Cached input tokens"),
		"cache_write_tokens": _("Cache write tokens"),
		"audio_tokens": _("Audio tokens"),
		"total_tokens": _("Total tokens"),
		"cost": _("Cost"),
	}


def _get_cost_breakdown_labels() -> dict[str, str]:
	return {
		"input": _("Input"),
		"output": _("Output"),
		"reasoning": _("Reasoning"),
		"cached": _("Cached"),
		"cache_write": _("Cache write"),
		"audio": _("Audio"),
		"image": _("Image"),
		"request": _("Request"),
	}


def _format_value(value, field_name: str) -> str:
	"""Format a field value for display."""
	if value is None:
		return "-"
	if isinstance(value, bool):
		return _("Yes") if value else _("No")
	if isinstance(value, datetime):
		return format_datetime(value)
	if isinstance(value, (int, float)):
		if field_name == "max_tokens" and value == 0:
			return _("unlimited")
		return str(value)
	if isinstance(value, str):
		return value
	return str(value)


# Fields hidden when value means "not set" per API convention (omit from requests).
# Only include params with universal semantics: 0 = no penalty/unlimited; None = not set.
# Exclude temperature, top_p: their defaults are model-specific.
_HIDE_WHEN_DEFAULT: dict[str, object] = {
	"frequency_penalty": 0,
	"presence_penalty": 0,
	"max_tokens": 0,
	"seed": None,
	"top_k": None,
	"stop": None,
}

# Fields shown only when a condition holds. Key -> predicate(block) -> bool.
_SHOW_WHEN: dict[str, Callable[[MessageBlock], bool]] = {
	"output_modality": lambda b: getattr(b, "output_modality", None) == "audio",
	"audio_voice": lambda b: getattr(b, "output_modality", None) == "audio",
	"audio_format": lambda b: getattr(b, "output_modality", None) == "audio",
	"reasoning_adaptive": lambda b: getattr(b, "reasoning_mode", False),
	"reasoning_budget_tokens": lambda b: (
		getattr(b, "reasoning_mode", False)
		and getattr(b, "reasoning_budget_tokens", None) is not None
	),
	"reasoning_effort": lambda b: (
		getattr(b, "reasoning_mode", False)
		and getattr(b, "reasoning_budget_tokens", None) is None
	),
	"system_index": lambda b: getattr(b, "system_index", None) is not None,
}


def _should_show_param(key: str, block: MessageBlock, val: object) -> bool:
	"""Only show params that are relevant and non-empty."""
	if key in _HIDE_WHEN_DEFAULT:
		default = _HIDE_WHEN_DEFAULT[key]
		if (default is None and val is None) or (
			default is not None and val == default
		):
			return False
	pred = _SHOW_WHEN.get(key)
	if pred is not None:
		return pred(block)
	if val is None:
		return False
	if isinstance(val, (list, dict)) and len(val) == 0:
		return False
	if val == "-":
		return False
	return True


def _format_request_section(block: MessageBlock) -> list[str]:
	"""Format request/block parameters section."""
	lines = section_header(_("Request"))
	excluded = {
		"request",
		"response",
		"db_id",
		"usage",
		"timing",
		"cost",
		"cost_breakdown",
	}
	data = block.model_dump(exclude=excluded)
	request_labels = _get_request_labels()

	model = block.model
	lines.append(
		f"{request_labels.get('model', 'Model')}: {model.provider_id}/{model.model_id}"
	)
	shown = {"model"}
	for key in request_labels:
		if key in shown or key in excluded or key not in data:
			continue
		val = data[key]
		if not _should_show_param(key, block, val):
			continue
		shown.add(key)
		lines.append(f"{request_labels[key]}: {_format_value(val, key)}")

	for key in sorted(data.keys()):
		if key in shown or key in excluded:
			continue
		val = data[key]
		if not _should_show_param(key, block, val):
			continue
		label = request_labels.get(key) or key.replace("_", " ").title()
		lines.append(f"{label}: {_format_value(val, key)}")
	return lines


def _usage_subset_lines(
	u,
	usage_labels: dict[str, str],
	total: int,
	input_total: int,
	output_total: int,
) -> list[str]:
	"""Build indented subset lines (reasoning, cached, cache_write, audio)."""

	def _pct_output(val: int | None) -> str:
		return (
			""
			if val is None or output_total == 0
			else f" ({100 * val / output_total:.1f}% of output)"
		)

	def _pct_input(val: int | None) -> str:
		return (
			""
			if val is None or input_total == 0
			else f" ({100 * val / input_total:.1f}% of input)"
		)

	sub: list[str] = []
	if u.reasoning_tokens and u.reasoning_tokens > 0:
		sub.append(
			f"  {usage_labels.get('reasoning_tokens', 'Reasoning tokens')}: {u.reasoning_tokens:,}{_pct_output(u.reasoning_tokens)}"
		)
	if u.cached_input_tokens and u.cached_input_tokens > 0:
		sub.append(
			f"  {usage_labels.get('cached_input_tokens', 'Cached input tokens')}: {u.cached_input_tokens:,}{_pct_input(u.cached_input_tokens)}"
		)
	if u.cache_write_tokens and u.cache_write_tokens > 0:
		sub.append(
			f"  {usage_labels.get('cache_write_tokens', 'Cache write tokens')}: {u.cache_write_tokens:,}{_pct_input(u.cache_write_tokens)}"
		)
	if u.audio_tokens and u.audio_tokens > 0:
		sub.append(
			f"  {usage_labels.get('audio_tokens', 'Audio tokens')}: {u.audio_tokens:,}{_pct_input(u.audio_tokens)}"
		)
	return sub


def _cost_breakdown_lines(block: MessageBlock) -> list[str]:
	"""Build cost breakdown subsection lines."""
	if not getattr(block, "cost_breakdown", None) or not block.cost_breakdown:
		return []
	breakdown_labels = _get_cost_breakdown_labels()
	breakdown_total = sum(block.cost_breakdown.values())
	lines = ["", _("Cost breakdown (by token type):")]
	for bkey, bval in sorted(block.cost_breakdown.items()):
		label = breakdown_labels.get(bkey, bkey.replace("_", " ").title())
		pct = (
			f" ({100 * bval / breakdown_total:.1f}%)" if breakdown_total else ""
		)
		lines.append(f"  {label}: ${bval:.6f}{pct}")
	return lines


def _format_usage_section(block: MessageBlock) -> list[str]:
	"""Format response consumption (usage) section."""
	lines = section_header(_("Response consumption"))
	if not block.usage:
		lines.append(_("(No usage data available)"))
		return lines

	u = block.usage
	usage_labels = _get_usage_labels()
	total = u.total_tokens if u.total_tokens is not None else u.effective_total
	input_total = u.input_tokens
	output_total = u.output_tokens

	def _pct_total(val: int | None) -> str:
		return (
			"" if val is None or total == 0 else f" ({100 * val / total:.1f}%)"
		)

	lines.append(
		f"{usage_labels.get('input_tokens', 'Input tokens')}: {input_total:,}{_pct_total(input_total)}"
	)
	lines.append(
		f"{usage_labels.get('output_tokens', 'Output tokens')}: {output_total:,}{_pct_total(output_total)}"
	)
	lines.extend(
		_usage_subset_lines(u, usage_labels, total, input_total, output_total)
	)
	lines.append(
		f"{usage_labels.get('total_tokens', 'Total tokens')}: {total:,}"
	)

	cost_val = block.cost if block.cost is not None else u.cost
	if cost_val is not None:
		lines.append(f"{usage_labels.get('cost', 'Cost')}: ${cost_val:.4f}")

	lines.extend(_cost_breakdown_lines(block))
	return lines


def _format_timing_section(block: MessageBlock) -> list[str]:
	"""Format timing section. Multi-line breakdown with percentages where useful."""
	lines = section_header(_("Timing"))
	t = block.timing
	if not t:
		lines.append(_("(No timing data available)"))
		return lines

	dur = t.duration_seconds
	gen_dur = t.generation_duration_seconds
	ttft = t.time_to_first_token_seconds
	send_dur = t.time_to_send_request_seconds

	# Main timing breakdown (one item per line for clarity)
	if dur is not None and dur > 0:
		lines.append(f"{_('Total duration')}: {dur:.2f} s")

		# Phase breakdown with percentages
		if send_dur is not None and send_dur >= 0:
			send_pct = 100 * send_dur / dur if dur else 0
			lines.append(
				f"  {_('Request sent in')}: {send_dur:.2f} s ({send_pct:.0f}%)"
			)
		if ttft is not None and ttft >= 0:
			ttft_pct = 100 * ttft / dur if dur else 0
			lines.append(
				f"  {_('Time to first token')} (TTFT): {ttft:.2f} s ({ttft_pct:.0f}%)"
			)
		if gen_dur is not None and gen_dur > 0:
			gen_pct = 100 * gen_dur / dur if dur else 0
			lines.append(
				f"  {_('Generation')}: {gen_dur:.2f} s ({gen_pct:.0f}%)"
			)
			if block.usage and block.usage.output_tokens > 0:
				tps = block.usage.output_tokens / gen_dur
				lines.append(f"    {_('Throughput')}: {tps:,.0f} tok/s")
		elif block.usage and block.usage.output_tokens > 0 and dur and dur > 0:
			tps = block.usage.output_tokens / dur
			lines.append(f"  {_('Throughput')}: {tps:,.0f} tok/s")
	elif dur is not None:
		lines.append(f"{_('Total duration')}: {dur:.2f} s")

	lines.append("")
	lines.extend(section_header(_("Timestamps")))
	if t.started_at:
		lines.append(f"{_('Started')}: {format_datetime(t.started_at)}")
	if t.request_sent_at:
		lines.append(
			f"{_('Request sent')}: {format_datetime(t.request_sent_at)}"
		)
	if t.finished_at:
		lines.append(f"{_('Finished')}: {format_datetime(t.finished_at)}")

	return lines


def _format_block_properties(block: MessageBlock) -> tuple[str, list[int]]:
	"""Format block properties as multiline text. Returns (text, section_line_indices)."""
	parts: list[str] = []
	sections: list[int] = []

	def _add_section(lines: list[str], sub_header: str | None = None) -> None:
		sections.append(len(parts))
		parts.extend(lines)
		parts.append("")
		if sub_header is not None:
			for i, line in enumerate(lines):
				if line == sub_header:
					sections.append(len(parts) - 1 - len(lines) + i)
					break

	_add_section(_format_request_section(block))
	_add_section(_format_usage_section(block))
	_add_section(_format_timing_section(block), _("Timestamps"))

	return "\n".join(parts).rstrip(), sections


class MessageBlockPropertiesDialog(SectionedPropertiesDialog):
	"""Dialog showing message block properties (model, params, usage, timing)."""

	def __init__(self, parent: wx.Window, block: MessageBlock):
		"""Initialize the dialog with message block properties."""
		text, sections = _format_block_properties(block)
		super().__init__(
			parent,
			title=_("Message block properties"),
			text=text,
			sections=sections,
			size=(600, 500),
		)
