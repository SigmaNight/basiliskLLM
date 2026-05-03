"""Structures for catalog AI models and lightweight export model references."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .provider import Provider, get_provider

getcontext().prec = 20

log = logging.getLogger(__name__)

_SUPPORTED_PARAMS_EXTRA_KEY = "supported_parameters"
_UNSUPPORTED_PARAMS_EXTRA_KEY = "unsupported_parameters"

_OPENAI_STYLE_REGULATED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
	{
		"temperature",
		"top_p",
		"max_tokens",
		"max_completion_tokens",
		"frequency_penalty",
		"presence_penalty",
		"seed",
		"stop",
		"n",
		"logit_bias",
		"logprobs",
		"top_logprobs",
		"response_format",
	}
)

_MAX_TOKEN_PARAM_ALIASES: frozenset[str] = frozenset(
	{"max_tokens", "max_completion_tokens", "max_output_tokens"}
)


def _normalized_str_set(raw: Any) -> frozenset[str] | None:
	if not isinstance(raw, list) or not raw:
		return None
	out = {
		str(x).strip().lower() for x in raw if x is not None and str(x).strip()
	}
	return frozenset(out) if out else None


def _metadata_supported_set(
	model: ProviderAIModel | None,
) -> frozenset[str] | None:
	if model is None:
		return None
	return _normalized_str_set(
		model.extra_info.get(_SUPPORTED_PARAMS_EXTRA_KEY)
	)


def _metadata_unsupported_set(model: ProviderAIModel | None) -> frozenset[str]:
	if model is None:
		return frozenset()
	raw = model.extra_info.get(_UNSUPPORTED_PARAMS_EXTRA_KEY)
	if not isinstance(raw, list):
		return frozenset()
	return frozenset(
		str(x).strip().lower() for x in raw if x is not None and str(x).strip()
	)


def model_allows_api_sampling_param(
	model: ProviderAIModel | None, api_param_name: str
) -> bool:
	"""Whether catalog metadata allows sending this sampling-related API field.

	``unsupported_parameters`` in ``extra_info`` rejects by name.
	When ``supported_parameters`` is non-empty, only listed names pass
	(plus max-token family aliases). Missing or empty metadata allows all.
	"""
	if model is None:
		return True
	name = api_param_name.strip().lower()
	if name in _metadata_unsupported_set(model):
		return False
	supported = _metadata_supported_set(model)
	if supported is None:
		return True
	if name in supported:
		return True
	if name in _MAX_TOKEN_PARAM_ALIASES:
		return bool(supported & _MAX_TOKEN_PARAM_ALIASES)
	return False


def strip_disallowed_completion_dict_params(
	model: ProviderAIModel | None,
	params: dict[str, Any],
	*,
	regulated_keys: frozenset[str] | None = None,
) -> None:
	"""Drop regulated top-level keys rejected by model metadata (in place).

	Args:
		model: Catalog model; may be None if metadata is unknown.
		params: Client request kwargs (e.g. OpenAI chat completion).
		regulated_keys: Candidate keys to evaluate; defaults to OpenAI-style
			sampling parameters only (never removes ``model``, ``messages``, …).
	"""
	if model is None:
		return
	keys = regulated_keys or _OPENAI_STYLE_REGULATED_TOP_LEVEL_KEYS
	for key in list(params):
		if key not in keys:
			continue
		if model_allows_api_sampling_param(model, key):
			continue
		params.pop(key, None)
		log.debug(
			"Omitted completion param %r for model %s (catalog metadata)",
			key,
			model.id,
		)


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
	if params := ex.get("supported_parameters"):
		consumed.add("supported_parameters")
		if isinstance(params, list) and params:
			joined = ", ".join(str(p) for p in params)
			# Translators: AI model details
			out.append(_("Supported parameters:") + f" {joined}")
	if _UNSUPPORTED_PARAMS_EXTRA_KEY in ex:
		consumed.add(_UNSUPPORTED_PARAMS_EXTRA_KEY)
		uparams = ex.get(_UNSUPPORTED_PARAMS_EXTRA_KEY)
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


def _build_provider_model_display_details(model: ProviderAIModel) -> str:
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


@dataclass
class ProviderAIModel:
	"""Provider AI Model dataclass.

	Attributes:
		id: The unique identifier of the AI model.
		name: The name of the AI model.
		description: The description of the AI model.
		context_window: The context window size of the AI model.
		max_output_tokens: The maximum number of output tokens for the AI model.
		max_temperature: The maximum temperature for the AI model.
		default_temperature: The default temperature for the AI model.
		reasoning: Whether the AI model supports reasoning.
		vision: Whether the AI model supports vision.
		created: Unix timestamp from model-metadata JSON (0 if unknown); used for sort order.
		extra_info: Additional information for the AI model.
	"""

	id: str
	name: str | None = field(default=None)
	description: str | None = field(default=None)
	context_window: int = field(default=0)
	max_output_tokens: int = field(default=-1)
	max_temperature: float = field(default=1.0)
	default_temperature: float = field(default=1.0)
	vision: bool = field(default=False)
	reasoning: bool = field(default=False)
	created: int = field(default=0)
	extra_info: dict[str, Any] = field(default_factory=dict)

	@property
	def display_name(self) -> str:
		"""Get the display name of the AI model.

		Returns:
			The display name of the AI model.
		"""
		return f"{self.name} ({self.id})" if self.name else self.id

	@property
	def display_model(self) -> tuple[str, str, str]:
		"""Row cells for the model list: name, vision, context, max output.

		Returns:
			(display_name, vision yes/no, context_window, max_output or "").
		"""
		return (
			self.display_name,
			_("yes") if self.vision else _("no"),
			str(self.context_window),
			str(self.max_output_tokens) if self.max_output_tokens > 0 else "",
		)

	@property
	def display_details(self) -> str:
		"""Get the display details of the AI model.

		Plain text for the model-details dialog: display name, fenced description
		when present, then limits (no separate Vision line), a single
		``Modality: …`` summary for every model, then features, provider metadata,
		leftover ``extra_info`` keys, and finally the ``Pricing:`` block when
		present. No trailing blank line.

		Returns:
			The display details of the AI model.
		"""
		return _build_provider_model_display_details(self)

	@property
	def effective_max_output_tokens(self) -> int:
		"""Calculates the effective maximum number of output tokens for the AI model.

		Returns the maximum output tokens based on the following logic:
		- If `max_output_tokens` is negative, returns the model's context window size
		- Otherwise, returns the explicitly set `max_output_tokens`

		Returns:
			The effective maximum number of output tokens
		"""
		if self.max_output_tokens < 0:
			return self.context_window
		return self.max_output_tokens


class AIModelInfo(BaseModel):
	"""AI Model information for exported content (e.g. conversation_profiles, conversation model).

	Attributes:
		provider_id: The unique identifier of the provider.
		model_id: The unique identifier of the AI model.
	"""

	provider_id: str = Field(pattern=r"^[a-zA-Z]+$")
	model_id: str = Field(pattern=r"^.+$")

	@staticmethod
	def get_provider_by_id(provider_id: str) -> Provider:
		"""Retrieve a provider instance by its unique identifier.

		Args:
			provider_id: The provider to retrieve.

		Returns:
			The ``Provider`` for ``provider_id``.

		Raises:
			ValueError: If no provider is found with the specified ID.
		"""
		return get_provider(id=provider_id)

	@field_validator("provider_id", mode="after")
	@classmethod
	def provider_must_exist(cls, value: str) -> str:
		"""Validates that a provider exists for the given provider ID.

		This class method checks the existence of a provider by attempting to retrieve it using the provided ID.
		If the provider is not found, a validation error will be raised.

		Args:
			value: The provider ID to validate.

		Returns:
			The original provider ID if a valid provider is found.

		Raises:
			ValueError: If no provider is found for the given provider ID.
		"""
		cls.get_provider_by_id(value)
		return value

	@property
	def provider(self) -> Provider:
		"""Retrieves the Provider instance associated with the current model's provider ID.

		Returns:
			Provider: The Provider instance corresponding to the model's provider_id.

		Raises:
			ValueError: If no Provider is found for the given provider_id.
		"""
		return self.get_provider_by_id(self.provider_id)
