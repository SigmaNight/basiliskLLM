"""Dialog for displaying AI model details with section navigation."""

from __future__ import annotations

import pprint
from typing import TYPE_CHECKING, Any

import wx

from .sectioned_properties_dialog import (
	SectionedPropertiesDialog,
	section_header,
)

if TYPE_CHECKING:
	from basilisk.provider_ai_model import ProviderAIModel


def _format_extra_value(value: Any, indent: str = "") -> list[str]:
	"""Format extra_info value for readable display (dict/list/str/None)."""
	if value is None:
		return [f"{indent}-"]
	if isinstance(value, bool):
		return [f"{indent}{_('Yes') if value else _('No')}"]
	if isinstance(value, str):
		return [f"{indent}{value}"] if value else [f"{indent}-"]
	if isinstance(value, (int, float)):
		return [f"{indent}{value}"]
	if isinstance(value, dict):
		lines_list: list[str] = []
		for k, v in sorted(value.items()):
			sub = _format_extra_value(v, indent + "  ")
			if len(sub) == 1:
				lines_list.append(f"{indent}{k}: {sub[0].strip()}")
			else:
				lines_list.append(f"{indent}{k}:")
				lines_list.extend(sub)
		return lines_list if lines_list else [f"{indent}-"]
	if isinstance(value, list):
		if not value:
			return [f"{indent}[]"]
		# Use pprint for simple lists (strings, numbers); recurse for nested
		if all(not isinstance(x, (dict, list)) for x in value):
			formatted = pprint.pformat(value, width=76)
			return [f"{indent}{line}" for line in formatted.split("\n")]
		lines = []
		for item in value:
			lines.extend(_format_extra_value(item, indent + "  "))
		return lines
	return [f"{indent}{pprint.pformat(value)}"]


def _find_section_indices(text: str) -> list[int]:
	"""Find line indices of section headers (unindented lines followed by underline)."""
	lines = text.split("\n")
	indices: list[int] = []
	for i, line in enumerate(lines):
		if (
			i + 1 < len(lines)
			and line
			and not line.startswith(" ")
			and lines[i + 1] == "-" * len(line)
		):
			indices.append(i)
	return indices


def _format_model_details(model: ProviderAIModel) -> tuple[str, list[int]]:
	"""Format model details as multiline text. Returns (text, section_line_indices)."""
	parts: list[str] = []

	def _yes_no(val: bool) -> str:
		return _("yes") if val else _("no")

	# Overview section
	overview = section_header(_("Overview"))
	overview.append(model.display_name)
	# Translators: AI model details
	overview.append(_("Vision:") + f" {_yes_no(model.vision)}")
	# Translators: AI model details
	overview.append(_("Audio:") + f" {_yes_no(model.audio)}")
	# Translators: AI model details
	overview.append(_("Document:") + f" {_yes_no(model.document)}")
	parts.extend(overview)
	parts.append("")

	# Limits section
	limits = section_header(_("Limits"))
	# Translators: AI model details
	limits.append(_("Context window:") + f" {model.context_window}")
	if model.max_output_tokens > 0:
		# Translators: AI model details
		limits.append(_("Max output tokens:") + f" {model.max_output_tokens}")
	parts.extend(limits)
	parts.append("")

	# Description section - split by newlines so each part is one logical line
	desc_lines = section_header(_("Description"))
	if model.description:
		desc_lines.extend(model.description.splitlines())
	else:
		desc_lines.append(_("(No description available)"))
	parts.extend(desc_lines)
	parts.append("")

	# Pricing section (only when model has usable pricing)
	if model.pricing and model.pricing.has_usable_pricing():
		pricing_lines = section_header(_("Pricing"))
		formatted = model.pricing.format_for_display()
		if formatted:
			for line in formatted.split("\n"):
				if line.strip():
					pricing_lines.append(line.strip())
		parts.extend(pricing_lines)
		parts.append("")

	# Extra info section (only if present; exclude Pricing to avoid duplication)
	extra_items = [
		(k, v) for k, v in model.extra_info.items() if k != "Pricing"
	]
	if extra_items:
		extra = section_header(_("Additional information"))
		for k, v in extra_items:
			formatted = _format_extra_value(v)
			if len(formatted) == 1:
				extra.append(f"{k}: {formatted[0].strip()}")
			else:
				extra.append(f"{k}:")
				for line in formatted:
					extra.append("  " + line)
		parts.extend(extra)
		parts.append("")

	text = "\n".join(parts).rstrip()
	sections = _find_section_indices(text)
	return text, sections


class ModelDetailsDialog(SectionedPropertiesDialog):
	"""Dialog showing AI model details with Page Up/Down section navigation."""

	def __init__(self, parent: wx.Window, model: ProviderAIModel):
		"""Initialize the dialog with model details."""
		text, sections = _format_model_details(model)
		super().__init__(
			parent,
			title=_("Model details"),
			text=text,
			sections=sections,
			size=(550, 450),
		)
