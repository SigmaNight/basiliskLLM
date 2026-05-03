"""Human-readable model details and pricing summaries for ``ProviderAIModel``.

Separated from :mod:`basilisk.provider_ai_model` so the core dataclass stays
small; this module is imported after ``ProviderAIModel`` is defined.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, getcontext
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
	from basilisk.provider_ai_model import ProviderAIModel

from basilisk.model_catalog_sampling import (
	SUPPORTED_PARAMETERS_EXTRA_KEY,
	UNSUPPORTED_PARAMETERS_EXTRA_KEY,
)
from basilisk.model_metadata_catalog import METADATA_CATALOG_EXTRA_KEY

getcontext().prec = 20


def summarize_pricing(pricing: dict[str, Any]) -> str:
	"""Format pricing map into human-readable model details text."""
	if not isinstance(pricing, dict):
		return ""
	lines: list[str] = []
	for usage_type, raw_price in sorted(pricing.items(), key=lambda kv: kv[0]):
		if raw_price is None:
			continue
		price = str(raw_price)
		if price == "0":
			continue
		try:
			if usage_type == "image":
				price_1k = round(Decimal(price) * Decimal(1000), 3)
				if price_1k == 0:
					continue
				lines.append(
					f"{usage_type}: ${price_1k}/K input imgs "
					f"(${price}/input img)"
				)
			else:
				price_1m = round(Decimal(price) * Decimal(1000000), 2)
				lines.append(
					f"{usage_type}: ${price_1m}/M tokens (${price}/token)"
				)
		except ArithmeticError:
			continue
	return "\n".join(lines)


def _yes_no_label(val: bool) -> str:
	return _("yes") if val else _("no")


def _details_description_lines(model: ProviderAIModel) -> list[str]:
	if not model.description:
		return []
	fence = f"```\n{model.description}\n```"
	# Empty string yields a blank line after the fence when joined.
	return [fence, ""]


def _details_limits_lines(model: ProviderAIModel) -> list[str]:
	out: list[str] = []
	# Translators: AI model details
	out.append(_("Context window:") + f" {model.context_window}")
	if model.max_output_tokens > 0:
		# Translators: AI model details
		out.append(_("Max output tokens:") + f" {model.max_output_tokens}")
	# Translators: AI model details
	out.append(_("Default temperature:") + f" {model.default_temperature}")
	return out


_MODALITY_CAPABILITY_KEYS: tuple[str, ...] = (
	"audio_input",
	"document_input",
	"video_input",
	"image_output",
	"audio_output",
	"video_output",
)

_MODALITY_TOKEN_ORDER: tuple[str, ...] = (
	"text",
	"image",
	"file",
	"audio",
	"video",
)


def _parse_modality_csv(raw: Any) -> set[str]:
	if not isinstance(raw, str):
		return set()
	return {p.strip().lower() for p in raw.split(",") if p.strip()}


def _format_modality_arrow(
	input_tokens: set[str], output_tokens: set[str]
) -> str:
	"""Return ``text+image->text`` style string; both sides include ``text``."""

	def side(tokens: set[str]) -> str:
		toks = set(tokens)
		toks.add("text")
		known = [t for t in _MODALITY_TOKEN_ORDER if t in toks]
		extra = sorted(t for t in toks if t not in _MODALITY_TOKEN_ORDER)
		parts = known + extra
		return "+".join(parts) if parts else "text"

	return f"{side(set(input_tokens))}->{side(set(output_tokens))}"


def _consume_extra_keys_if_present(
	ex: dict[str, Any], consumed: set[str], keys: tuple[str, ...]
) -> None:
	for k in keys:
		if k in ex:
			consumed.add(k)


def _modality_io_token_sets(
	model: ProviderAIModel, ex: dict[str, Any]
) -> tuple[set[str], set[str], tuple[str, ...]]:
	"""Input/output modality token sets and ``extra_info`` keys to mark consumed."""
	im_raw = ex.get("input_modalities")
	om_raw = ex.get("output_modalities")
	has_csv = (isinstance(im_raw, str) and im_raw.strip()) or (
		isinstance(om_raw, str) and om_raw.strip()
	)
	if has_csv:
		in_t = _parse_modality_csv(im_raw)
		out_t = _parse_modality_csv(om_raw)
		if not in_t:
			in_t = {"text"}
		if not out_t:
			out_t = {"text"}
		if model.vision:
			in_t.add("image")
		csv_keys = tuple(
			k for k in ("input_modalities", "output_modalities") if k in ex
		)
		return in_t, out_t, csv_keys
	in_t = {"text"}
	out_t = {"text"}
	if model.vision:
		in_t.add("image")
	if ex.get("document_input"):
		in_t.add("file")
	if ex.get("audio_input"):
		in_t.add("audio")
	if ex.get("video_input"):
		in_t.add("video")
	if ex.get("image_output"):
		out_t.add("image")
	if ex.get("audio_output"):
		out_t.add("audio")
	if ex.get("video_output"):
		out_t.add("video")
	return in_t, out_t, ()


def _details_modality_lines(
	model: ProviderAIModel, ex: dict[str, Any], consumed: set[str]
) -> list[str]:
	"""Single ``Modality: left->right`` line (catalog route, CSV, or inferred)."""
	if mr := ex.get("modality_route"):
		consumed.add("modality_route")
		_consume_extra_keys_if_present(ex, consumed, _MODALITY_CAPABILITY_KEYS)
		_consume_extra_keys_if_present(
			ex, consumed, ("input_modalities", "output_modalities")
		)
		# Translators: AI model details (I/O modality summary)
		return [_("Modality:") + f" {mr}"]

	in_t, out_t, csv_keys = _modality_io_token_sets(model, ex)
	for k in csv_keys:
		consumed.add(k)
	_consume_extra_keys_if_present(ex, consumed, _MODALITY_CAPABILITY_KEYS)
	route = _format_modality_arrow(in_t, out_t)
	# Translators: AI model details (I/O modality summary)
	return [_("Modality:") + f" {route}"]


def _details_feature_lines(
	model: ProviderAIModel, ex: dict[str, Any], consumed: set[str]
) -> list[str]:
	out: list[str] = []
	if cs := ex.get(METADATA_CATALOG_EXTRA_KEY):
		consumed.add(METADATA_CATALOG_EXTRA_KEY)
		# Translators: AI model details (catalog origin label)
		out.append(_("Metadata catalog:") + f" {cs}")
	if params := ex.get(SUPPORTED_PARAMETERS_EXTRA_KEY):
		consumed.add(SUPPORTED_PARAMETERS_EXTRA_KEY)
		if isinstance(params, list) and params:
			joined = ", ".join(str(p) for p in params)
			# Translators: AI model details
			out.append(_("Supported parameters:") + f" {joined}")
	if UNSUPPORTED_PARAMETERS_EXTRA_KEY in ex:
		consumed.add(UNSUPPORTED_PARAMETERS_EXTRA_KEY)
		uparams = ex.get(UNSUPPORTED_PARAMETERS_EXTRA_KEY)
		if isinstance(uparams, list) and uparams:
			joined = ", ".join(str(p) for p in uparams)
			# Translators: AI model details
			out.append(_("Unsupported parameters:") + f" {joined}")
	if "web_search_capable" in ex:
		consumed.add("web_search_capable")
		# Translators: AI model details
		out.append(
			_("Web search capable:")
			+ " "
			+ _yes_no_label(bool(ex["web_search_capable"]))
		)
	# Translators: AI model details
	reasoning_one_line = _("Reasoning:") + " " + _yes_no_label(model.reasoning)
	if "reasoning_capable" in ex:
		consumed.add("reasoning_capable")
		meta_rc = bool(ex["reasoning_capable"])
		if meta_rc != model.reasoning:
			# Translators: AI model details (metadata vs thinking row selection)
			out.append(
				_("Reasoning-capable (metadata):")
				+ " "
				+ _yes_no_label(meta_rc)
			)
			# Translators: AI model details (effective reasoning flag on model)
			out.append(
				_("Reasoning (selected variant):")
				+ " "
				+ _yes_no_label(model.reasoning)
			)
		else:
			out.append(reasoning_one_line)
	else:
		out.append(reasoning_one_line)
	return out


def _details_pricing_lines(ex: dict[str, Any], consumed: set[str]) -> list[str]:
	"""Summarized rates under a ``Pricing:`` label (``extra_info`` uses key ``Pricing``)."""
	summ_text = ex.get("Pricing")
	if not summ_text and isinstance(ex.get("pricing_rates"), dict):
		summ_text = summarize_pricing(ex["pricing_rates"])
	if not summ_text:
		return []
	if "Pricing" in ex:
		consumed.add("Pricing")
	if "pricing_rates" in ex:
		consumed.add("pricing_rates")
	if isinstance(ex.get("pricing"), dict):
		consumed.add("pricing")
	text = summ_text if isinstance(summ_text, str) else str(summ_text)
	body: list[str] = []
	for line in text.splitlines():
		st = line.strip()
		if st:
			body.append(st)
	if not body:
		return []
	# Translators: Section label before per-rate lines in model details
	title = _("Pricing:")
	indented = [f"  {line}" for line in body]
	# Blank line before the block, then blank before following section.
	return ["", title, *indented, ""]


def _details_provider_lines(
	model: ProviderAIModel, ex: dict[str, Any], consumed: set[str]
) -> list[str]:
	out: list[str] = []
	if tok := ex.get("tokenizer"):
		consumed.add("tokenizer")
		# Translators: AI model details
		out.append(_("Tokenizer:") + f" {tok}")
	if it := ex.get("instruct_type"):
		consumed.add("instruct_type")
		# Translators: AI model details
		out.append(_("Instruct type:") + f" {it}")
	if "is_moderated" in ex:
		consumed.add("is_moderated")
		im = ex["is_moderated"]
		# Translators: AI model details
		out.append(_("Provider-moderated:") + " " + _yes_no_label(bool(im)))
	catalog: str | None = None
	if model.created:
		try:
			catalog = datetime.fromtimestamp(model.created).strftime(
				"%Y-%m-%d %H:%M:%S"
			)
		except OSError, OverflowError, ValueError:
			catalog = None
	if not catalog and isinstance(ex.get("created"), str):
		st = ex["created"].strip()
		if st:
			catalog = st
	if catalog:
		if "created" in ex:
			consumed.add("created")
		# Translators: AI model details (release / catalog timestamp)
		out.append(_("Catalog created:") + f" {catalog}")
	return out


def _details_remaining_lines(
	ex: dict[str, Any], consumed: set[str]
) -> list[str]:
	return [f"{k}: {ex[k]}" for k in sorted(ex.keys()) if k not in consumed]


def _flatten_detail_parts(parts: list[list[str]]) -> list[str]:
	"""Join non-empty detail segments without stacking duplicate blank lines."""
	lines: list[str] = []
	for part in parts:
		if not part:
			continue
		if lines and lines[-1] == "" and part[0] == "":
			lines.extend(part[1:])
		else:
			lines.extend(part)
	return lines


def _trim_trailing_blank_lines(lines: list[str]) -> None:
	"""Drop empty trailing entries so the dialog has no blank line at EOF."""
	while lines and lines[-1] == "":
		lines.pop()


def build_provider_model_display_details(model: ProviderAIModel) -> str:
	"""Build plain-text model details for the read-only dialog."""
	ex = model.extra_info
	consumed: set[str] = set()
	parts: list[list[str]] = [
		[model.display_name, ""],
		_details_description_lines(model),
		_details_limits_lines(model),
		_details_modality_lines(model, ex, consumed),
		_details_feature_lines(model, ex, consumed),
		_details_provider_lines(model, ex, consumed),
	]
	# Run pricing before ``remaining`` so price keys stay out of leftover lines,
	# but append the pricing block last in the dialog.
	pricing_part = _details_pricing_lines(ex, consumed)
	parts.append(_details_remaining_lines(ex, consumed))
	parts.append(pricing_part)
	lines = _flatten_detail_parts(parts)
	_trim_trailing_blank_lines(lines)
	return "\n".join(lines)
