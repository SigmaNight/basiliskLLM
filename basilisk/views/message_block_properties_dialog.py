"""Dialog for displaying message block properties (request, response, usage, timing)."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

import wx

from basilisk.conversation.conversation_model import MessageBlock


def _get_request_labels() -> dict[str, str]:
	"""Field name -> display label. Add new MessageBlock fields for automatic display."""
	return {
		"model": _("Model"),
		"temperature": _("Temperature"),
		"max_tokens": _("Max tokens"),
		"top_p": _("Top P"),
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
		"total_tokens": _("Total tokens"),
	}


def _format_value(value, field_name: str) -> str:
	"""Format a field value for display."""
	if value is None:
		return "-"
	if isinstance(value, bool):
		return _("Yes") if value else _("No")
	if isinstance(value, datetime):
		return value.isoformat()
	if isinstance(value, (int, float)):
		if field_name == "max_tokens" and value == 0:
			return _("unlimited")
		return str(value)
	if isinstance(value, str):
		return value
	return str(value)


# Fields shown only when a condition holds. Key -> predicate(block) -> bool.
# Omit empty/inappropriate fields (e.g. reasoning sub-fields when reasoning_mode is off).
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
	pred = _SHOW_WHEN.get(key)
	if pred is not None:
		return pred(block)
	if val is None:
		return False
	if val == "-":
		return False
	return True


def _format_request_section(block: MessageBlock) -> list[str]:
	"""Format request/block parameters section."""
	lines = [_("Request"), "-" * 40]
	excluded = {"request", "response", "db_id", "usage", "timing"}
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


def _format_usage_section(block: MessageBlock) -> list[str]:
	"""Format response consumption (usage) section."""
	lines = [_("Response consumption"), "-" * 40]
	if not block.usage:
		lines.append(_("(No usage data available)"))
		return lines

	u = block.usage
	usage_labels = _get_usage_labels()
	usage_items = [
		("input_tokens", u.input_tokens),
		("output_tokens", u.output_tokens),
	]
	if u.reasoning_tokens is not None:
		usage_items.append(("reasoning_tokens", u.reasoning_tokens))
	if u.cached_input_tokens is not None:
		usage_items.append(("cached_input_tokens", u.cached_input_tokens))
	total = u.total_tokens if u.total_tokens is not None else u.effective_total
	usage_items.append(("total_tokens", total))
	for key, val in usage_items:
		lines.append(f"{usage_labels.get(key, key)}: {_format_value(val, key)}")
	return lines


def _format_timing_summary(block: MessageBlock) -> str | None:
	"""Build concise timing summary line. Returns None if no timing."""
	t = block.timing
	if not t:
		return None
	dur = t.duration_seconds
	gen_dur = t.generation_duration_seconds
	ttft = t.time_to_first_token_seconds
	send_dur = t.time_to_send_request_seconds

	parts = []
	if dur is not None:
		parts.append(f"{_('Duration')}: {dur:.2f} s")
	if gen_dur is not None and gen_dur > 0:
		parts.append(f"{_('generated in')} {gen_dur:.2f} s")

	if block.usage and block.usage.output_tokens > 0:
		rate_dur = gen_dur if gen_dur and gen_dur > 0 else dur
		if rate_dur is not None and rate_dur > 0:
			tps = block.usage.output_tokens / rate_dur
			parts.append(f"{tps:.1f} tok/s")
			if gen_dur is None and dur:
				parts.append(f"({_('includes TTFT')})")

	extra = []
	if ttft is not None:
		extra.append(f"{_('TTFT')}: {ttft:.2f} s")
	if send_dur is not None:
		extra.append(f"{_('request sent in')} {send_dur:.2f} s")
	if extra:
		parts.append(f"({', '.join(extra)})")

	return ", ".join(parts) if parts else None


def _format_timing_section(block: MessageBlock) -> list[str]:
	"""Format timing section. Concise summary plus timestamps."""
	lines = [_("Timing"), "-" * 40]
	if not block.timing:
		lines.append(_("(No timing data available)"))
		return lines

	summary = _format_timing_summary(block)
	if summary:
		lines.append(summary)

	t = block.timing
	if t.started_at:
		lines.append(f"{_('Started')}: {t.started_at.isoformat()}")
	if t.request_sent_at:
		lines.append(f"{_('Request sent')}: {t.request_sent_at.isoformat()}")
	if t.finished_at:
		lines.append(f"{_('Finished')}: {t.finished_at.isoformat()}")

	return lines


def _format_block_properties(block: MessageBlock) -> str:
	"""Format block properties as multiline text. Generic over MessageBlock fields."""
	parts = []
	parts.extend(_format_request_section(block))
	parts.append("")
	parts.extend(_format_usage_section(block))
	parts.append("")
	parts.extend(_format_timing_section(block))
	return "\n".join(parts)


class MessageBlockPropertiesDialog(wx.Dialog):
	"""Dialog showing message block properties (model, params, usage, timing)."""

	def __init__(self, parent: wx.Window, block: MessageBlock):
		"""Initialize the dialog.

		Args:
			parent: Parent window.
			block: The message block to display properties for.
		"""
		super().__init__(
			parent,
			title=_("Message block properties"),
			size=(600, 500),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		text = _format_block_properties(block)
		text_ctrl = wx.TextCtrl(
			self,
			value=text,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_NONE,
		)
		text_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

		vbox = wx.BoxSizer(wx.VERTICAL)
		vbox.Add(text_ctrl, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
		close_btn = wx.Button(self, id=wx.ID_CLOSE)
		close_btn.Bind(wx.EVT_BUTTON, lambda _: self.Close())
		close_btn.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
		vbox.Add(
			close_btn, proportion=0, flag=wx.ALIGN_CENTER | wx.ALL, border=10
		)
		self.SetSizer(vbox)

	def _on_key_down(self, event: wx.KeyEvent):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self.Close()
		else:
			event.Skip()
