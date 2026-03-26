"""Dialog for displaying conversation-level properties (token usage, dates, etc.)."""

from __future__ import annotations

from datetime import datetime

import wx

from basilisk.conversation.conversation_model import Conversation

from .sectioned_properties_dialog import (
	SectionedPropertiesDialog,
	format_datetime,
	section_header,
)


def _format_value(value, field_name: str) -> str:
	"""Format a field value for display."""
	if value is None:
		return "-"
	if isinstance(value, bool):
		return _("Yes") if value else _("No")
	if isinstance(value, datetime):
		return format_datetime(value)
	if isinstance(value, (int, float)):
		return str(value)
	if isinstance(value, str):
		return value
	if isinstance(value, list):
		return ", ".join(str(v) for v in value)
	return str(value)


def _token_usage_items(conversation: Conversation) -> list[tuple[str, str]]:
	"""Build token usage section items."""
	total = conversation.token_total
	if total == 0:
		return [("", _("(No usage data available)"))]
	input_total = conversation.input_tokens_total
	output_total = conversation.output_tokens_total

	def _pct_total(val: int) -> str:
		return f" ({100 * val / total:.1f}%)" if total else ""

	def _pct_output(val: int) -> str:
		return (
			f" ({100 * val / output_total:.1f}% of output)"
			if output_total
			else ""
		)

	def _pct_input(val: int) -> str:
		return (
			f" ({100 * val / input_total:.1f}% of input)" if input_total else ""
		)

	items: list[tuple[str, str]] = [
		(_("Total tokens"), f"{total:,}"),
		(
			_("Average per block"),
			f"{conversation.average_tokens_per_block:,.1f}",
		),
		(_("Input tokens"), f"{input_total:,}{_pct_total(input_total)}"),
		(_("Output tokens"), f"{output_total:,}{_pct_total(output_total)}"),
	]
	if conversation.reasoning_tokens_total > 0:
		items.append(
			(
				_("Reasoning tokens"),
				f"{conversation.reasoning_tokens_total:,}{_pct_output(conversation.reasoning_tokens_total)}",
			)
		)
	if conversation.cached_input_tokens_total > 0:
		items.append(
			(
				_("Cached input tokens"),
				f"{conversation.cached_input_tokens_total:,}{_pct_input(conversation.cached_input_tokens_total)}",
			)
		)
	if conversation.cache_write_tokens_total > 0:
		items.append(
			(
				_("Cache write tokens"),
				f"{conversation.cache_write_tokens_total:,}{_pct_input(conversation.cache_write_tokens_total)}",
			)
		)
	if conversation.audio_tokens_total > 0:
		items.append(
			(
				_("Audio tokens"),
				f"{conversation.audio_tokens_total:,}{_pct_input(conversation.audio_tokens_total)}",
			)
		)
	return items


def _cost_items(
	conversation: Conversation, cost_total: float | None, total: int
) -> list[tuple[str, str]]:
	"""Build estimated cost section items."""
	if cost_total is None:
		return [
			(
				"",
				_("(Not available — only OpenRouter reports cost per request)"),
			)
		]
	items: list[tuple[str, str]] = [(_("Total"), f"${cost_total:.4f}")]
	if total > 0:
		items.append(
			(_("Mean per MTok"), f"${1_000_000 * cost_total / total:.4f}/M")
		)
	if conversation.block_count > 1:
		items.append(
			(
				_("Mean per block"),
				f"${cost_total / conversation.block_count:.6f}",
			)
		)
	return items


def _models_items(
	conversation: Conversation, total: int, cost_total: float | None
) -> list[tuple[str, str]]:
	"""Build models used section items."""
	models_used = conversation.models_used
	if not models_used:
		return []
	if len(models_used) == 1:
		return [("", f"• {models_used[0]}")]

	model_tokens: dict[str, int] = {}
	model_blocks: dict[str, int] = {}
	model_cost: dict[str, float] = {}
	for block in conversation.messages:
		key = f"{block.model.provider_id}/{block.model.model_id}"
		model_blocks[key] = model_blocks.get(key, 0) + 1
		if block.usage:
			model_tokens[key] = (
				model_tokens.get(key, 0) + block.usage.effective_total
			)
		c = (
			block.cost
			if block.cost is not None
			else (
				block.usage.cost
				if block.usage and block.usage.cost is not None
				else None
			)
		)
		if c is not None:
			model_cost[key] = model_cost.get(key, 0) + c

	model_items: list[tuple[str, str]] = []
	for model in models_used:
		tok = model_tokens.get(model, 0)
		blk = model_blocks.get(model, 0)
		cst = model_cost.get(model)
		tok_pct = f" ({100 * tok / total:.1f}%)" if total else ""
		blk_pct = (
			f" ({100 * blk / conversation.block_count:.1f}%)"
			if conversation.block_count
			else ""
		)
		val = f"{tok:,} tok{tok_pct}, {blk} block(s){blk_pct}"
		if cst is not None and cost_total and cost_total > 0:
			val += f", ${cst:.4f} ({100 * cst / cost_total:.1f}%)"
		model_items.append((f"• {model}", val))
	return model_items


def _timestamps_items(conversation: Conversation) -> list[tuple[str, str]]:
	"""Build timestamps section items."""
	started = conversation.started_at
	last_activity = conversation.last_activity_at
	duration = conversation.total_duration_seconds
	items: list[tuple[str, str]] = [
		(_("Started"), _format_value(started, "started_at")),
		(_("Last activity"), _format_value(last_activity, "last_activity_at")),
	]
	if duration is not None:
		if duration >= 3600:
			items.append((_("Total duration"), f"{duration / 3600:.1f} h"))
		elif duration >= 60:
			items.append((_("Total duration"), f"{duration / 60:.1f} min"))
		else:
			items.append((_("Total duration"), f"{duration:.1f} s"))
	return items


def _format_conversation_properties(
	conversation: Conversation,
) -> tuple[str, list[int]]:
	"""Format conversation properties as plain text.

	Returns (text, section_line_indices) for display and Page Up/Down navigation.
	"""
	lines: list[str] = []
	sections: list[int] = []

	def _section(name: str, items: list[tuple[str, str]] | None = None) -> None:
		sections.append(len(lines))
		lines.extend(section_header(name))
		if items:
			for label, value in items:
				lines.append(value if not label else f"{label}: {value}")
		lines.append("")

	total = conversation.token_total
	cost_total = conversation.cost_total

	_section(
		_("Overview"),
		[
			(_("Title"), conversation.title or _("Untitled")),
			(_("Block count"), str(conversation.block_count)),
		],
	)
	_section(_("Token usage"), _token_usage_items(conversation))
	_section(_("Estimated cost"), _cost_items(conversation, cost_total, total))
	if conversation.models_used:
		_section(
			_("Models used"), _models_items(conversation, total, cost_total)
		)
	_section(_("Timestamps"), _timestamps_items(conversation))

	text = "\n".join(lines).rstrip()
	return text, sections


class ConversationPropertiesDialog(SectionedPropertiesDialog):
	"""Dialog showing conversation-level properties (token usage, dates, models)."""

	def __init__(self, parent: wx.Window, conversation: Conversation):
		"""Initialize the dialog with conversation properties."""
		text, sections = _format_conversation_properties(conversation)
		super().__init__(
			parent,
			title=_("Conversation properties"),
			text=text,
			sections=sections,
			size=(550, 450),
		)
