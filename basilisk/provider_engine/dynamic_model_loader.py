"""Module for loading model metadata from JSON URLs.

Provides reusable fetch and parse logic for providers that use the
model-metadata JSON format (OpenAI, Anthropic, xAI, Mistral, etc.).

Schema reference: https://github.com/SigmaNight/model-metadata — each model
has ``architecture.modality`` (e.g. ``text+image+file->text`` or
``text+audio->text+audio``), plus ``input_modalities`` / ``output_modalities``
arrays. We merge string and array signals so flags match upstream JSON.
"""

from __future__ import annotations

import logging
import time
from enum import StrEnum, auto
from typing import Any, Iterator

import httpx
from pydantic import (
	BaseModel,
	ConfigDict,
	Field,
	StrictStr,
	ValidationError,
	field_validator,
	model_validator,
)

from basilisk.consts import APP_NAME, APP_SOURCE_URL
from basilisk.provider_ai_model import ProviderAIModel

log = logging.getLogger(__name__)

_CACHE: dict[str, tuple[list[ProviderAIModel], float]] = {}
_LAST_LOAD_ERROR: dict[str, str | None] = {}


class ArchitectureModalityToken(StrEnum):
	"""Tokens in ``modality`` strings and modality arrays (lowercase per schema)."""

	TEXT = auto()
	IMAGE = auto()
	FILE = auto()
	AUDIO = auto()
	VIDEO = auto()


class SupportedApiParameter(StrEnum):
	"""``supported_parameters`` entries we interpret for capabilities."""

	REASONING = auto()
	INCLUDE_REASONING = auto()
	TOOLS = auto()


class ModelExtraInfoKey(StrEnum):
	"""Keys stored in ``ProviderAIModel.extra_info`` for loader-derived data."""

	SUPPORTED_PARAMETERS = auto()
	REASONING_CAPABLE = auto()
	WEB_SEARCH_CAPABLE = auto()
	AUDIO_INPUT = auto()
	DOCUMENT_INPUT = auto()
	VIDEO_INPUT = auto()
	IMAGE_OUTPUT = auto()
	AUDIO_OUTPUT = auto()
	VIDEO_OUTPUT = auto()


_MODALITY_ARROW = "->"
_MODALITY_SEPARATOR = "+"

# HTTP client
_HTTP_TIMEOUT_SECONDS = 30.0

# Schema does not expose max temperature; keep aligned with prior static model lists.
_DEFAULT_MAX_TEMPERATURE_FROM_METADATA = 2.0

# When ``default_parameters.temperature`` is null or absent; matches ProviderAIModel default.
_FALLBACK_DEFAULT_TEMPERATURE = 1.0
_DEFAULT_CONTEXT_WINDOW = 0
_DEFAULT_MAX_OUTPUT_TOKENS = -1


class ModalityCapabilities(BaseModel):
	"""Inferred I/O capabilities for one model (before mapping to ``ProviderAIModel``)."""

	model_config = ConfigDict(extra="forbid", frozen=True)

	vision: bool
	audio_input: bool
	document_input: bool
	video_input: bool
	image_output: bool
	audio_output: bool
	video_output: bool


class ArchitectureMetadata(BaseModel):
	"""Typed architecture metadata used for modality inference."""

	model_config = ConfigDict(extra="ignore")

	modality: str | None = None
	input_modalities: list[str] = Field(default_factory=list)
	output_modalities: list[str] = Field(default_factory=list)

	@field_validator("modality", mode="before")
	@classmethod
	def _normalize_modality(cls, value: Any) -> str | None:
		if value is None:
			return None
		return str(value)

	@field_validator("input_modalities", "output_modalities", mode="before")
	@classmethod
	def _normalize_modalities(cls, value: Any) -> list[str]:
		if not isinstance(value, list):
			return []
		return [str(v) for v in value if str(v).strip()]


class TopProviderMetadata(BaseModel):
	"""Typed subset of top_provider values used for limits."""

	model_config = ConfigDict(extra="ignore")

	context_length: int | None = None
	max_completion_tokens: int | None = None

	@field_validator("context_length", "max_completion_tokens", mode="before")
	@classmethod
	def _to_int_or_none(cls, value: Any) -> int | None:
		try:
			return int(value)
		except TypeError, ValueError:
			return None


class DefaultParametersMetadata(BaseModel):
	"""Typed subset of default_parameters used by Basilisk."""

	model_config = ConfigDict(extra="ignore")

	temperature: float | None = None

	@field_validator("temperature", mode="before")
	@classmethod
	def _to_float_or_none(cls, value: Any) -> float | None:
		if isinstance(value, bool) or value is None:
			return None
		if isinstance(value, (int, float)):
			return float(value)
		return None


class ModelMetadataItem(BaseModel):
	"""Validated view of one model row from model-metadata JSON."""

	model_config = ConfigDict(extra="ignore")

	id: StrictStr
	name: str | None = None
	description: str | None = None
	created: int = 0
	architecture: ArchitectureMetadata = Field(
		default_factory=ArchitectureMetadata
	)
	top_provider: TopProviderMetadata = Field(
		default_factory=TopProviderMetadata
	)
	default_parameters: DefaultParametersMetadata = Field(
		default_factory=DefaultParametersMetadata
	)
	supported_parameters: list[str] = Field(default_factory=list)
	supports_web_search: bool | None = None

	@model_validator(mode="before")
	@classmethod
	def _normalize_struct_fields(cls, value: Any) -> Any:
		"""Coerce malformed nested values to safe defaults before validation."""
		if not isinstance(value, dict):
			return value
		data = dict(value)
		for key in ("architecture", "top_provider", "default_parameters"):
			if not isinstance(data.get(key), dict):
				data[key] = {}
		if not isinstance(data.get("supported_parameters"), list):
			data["supported_parameters"] = []
		elif data["supported_parameters"] is not None:
			data["supported_parameters"] = [
				str(v) for v in data["supported_parameters"]
			]
		if not isinstance(data.get("supports_web_search"), bool):
			data["supports_web_search"] = None
		return data

	@field_validator("created", mode="before")
	@classmethod
	def _normalize_created(cls, value: Any) -> int:
		try:
			return int(value)
		except TypeError, ValueError:
			return 0


def fetch_models_json(url: str) -> dict[str, Any]:
	"""Fetch model metadata JSON from URL.

	Args:
		url: URL to fetch (e.g. model-metadata JSON).

	Returns:
		Parsed JSON dict with "models" key containing model list.

	Raises:
		httpx.HTTPError: On request failure.
	"""
	response = httpx.get(
		url,
		headers={"User-Agent": f"{APP_NAME} ({APP_SOURCE_URL})"},
		timeout=_HTTP_TIMEOUT_SECONDS,
	)
	response.raise_for_status()
	return response.json()


def _get_max_completion_tokens(top_provider: TopProviderMetadata) -> int:
	"""Extract max_completion_tokens from top_provider, or -1 if absent."""
	if top_provider.max_completion_tokens is None:
		return _DEFAULT_MAX_OUTPUT_TOKENS
	return top_provider.max_completion_tokens


def _get_context_length(top_provider: TopProviderMetadata) -> int:
	"""Extract context_length from top_provider only (no top-level fallback)."""
	if top_provider.context_length is None:
		return _DEFAULT_CONTEXT_WINDOW
	return top_provider.context_length


def _normalize_modalities_list(raw: Any) -> set[str]:
	"""Lowercase modality tokens from JSON list."""
	if not isinstance(raw, list):
		return set()
	out: set[str] = set()
	for m in raw:
		s = str(m).strip().lower()
		if s:
			out.add(s)
	return out


def _parse_modality_arrow_string(modality: str) -> tuple[set[str], set[str]]:
	"""Split ``architecture.modality`` into input and output token sets.

	Examples from model-metadata:
	- ``text+image+file->text`` → inputs {text, image, file}, outputs {text}
	- ``text+audio->text+audio`` → both sides carry audio for I/O
	- ``text+image->text+image`` → image on input and output (e.g. Gemini)
	"""
	s = (modality or "").lower().strip()
	if not s:
		return set(), set()
	if _MODALITY_ARROW in s:
		left, right = s.split(_MODALITY_ARROW, 1)
		in_toks = {
			t.strip() for t in left.split(_MODALITY_SEPARATOR) if t.strip()
		}
		out_toks = {
			t.strip() for t in right.split(_MODALITY_SEPARATOR) if t.strip()
		}
		return in_toks, out_toks
	in_toks = {t.strip() for t in s.split(_MODALITY_SEPARATOR) if t.strip()}
	return in_toks, set()


def _extract_io_modalities(
	architecture: ArchitectureMetadata,
) -> tuple[set[str], set[str]]:
	"""Extract normalized input/output modality tokens from all schema fields."""
	in_str, out_str = _parse_modality_arrow_string(architecture.modality or "")
	input_mods = _normalize_modalities_list(architecture.input_modalities)
	output_mods = _normalize_modalities_list(architecture.output_modalities)
	return in_str | input_mods, out_str | output_mods


def _infer_modality_capabilities(
	architecture: ArchitectureMetadata,
) -> ModalityCapabilities:
	"""Derive I/O flags from modality string and modality lists."""
	input_tokens, output_tokens = _extract_io_modalities(architecture)

	def has_in(token: ArchitectureModalityToken) -> bool:
		return token.value in input_tokens

	def has_out(token: ArchitectureModalityToken) -> bool:
		return token.value in output_tokens

	return ModalityCapabilities(
		vision=has_in(ArchitectureModalityToken.IMAGE),
		audio_input=has_in(ArchitectureModalityToken.AUDIO),
		document_input=has_in(ArchitectureModalityToken.FILE),
		video_input=has_in(ArchitectureModalityToken.VIDEO),
		image_output=has_out(ArchitectureModalityToken.IMAGE),
		audio_output=has_out(ArchitectureModalityToken.AUDIO),
		video_output=has_out(ArchitectureModalityToken.VIDEO),
	)


def _supports_basilisk_text_output(architecture: ArchitectureMetadata) -> bool:
	"""Return whether a model can produce text output used by Basilisk UI.

	If output modalities are explicitly provided (either in ``modality`` arrow
	string or ``output_modalities``), require ``text`` to be present.
	When output is not explicit in metadata, assume text output for compatibility.
	"""
	_, output_tokens = _extract_io_modalities(architecture)
	if not output_tokens:
		return True
	return ArchitectureModalityToken.TEXT.value in output_tokens


def _has_reasoning_capable(supported: list[str]) -> bool:
	rp = SupportedApiParameter.REASONING.value
	ir = SupportedApiParameter.INCLUDE_REASONING.value
	return rp in supported or ir in supported


def _has_web_search_capable(
	explicit: bool | None, supported: list[str]
) -> bool:
	if explicit is True:
		return True
	if explicit is False:
		return False
	return SupportedApiParameter.TOOLS.value in supported


def _default_temperature(
	default_parameters: DefaultParametersMetadata,
) -> float:
	"""Use numeric ``default_parameters.temperature`` when present."""
	if default_parameters.temperature is None:
		return _FALLBACK_DEFAULT_TEMPERATURE
	return default_parameters.temperature


def _iter_valid_model_items(raw: dict[str, Any]) -> Iterator[ModelMetadataItem]:
	"""Validate model rows with pydantic and skip invalid entries."""
	model_list = raw.get("models")
	if not isinstance(model_list, list):
		return
	for row in model_list:
		if not isinstance(row, dict):
			continue
		try:
			item = ModelMetadataItem.model_validate(row)
		except ValidationError:
			continue
		if not item.id:
			continue
		yield item


def _extra_info_from_modalities(m: ModalityCapabilities) -> dict[str, bool]:
	"""Map inferred modalities to ``extra_info`` booleans."""
	return {
		ModelExtraInfoKey.AUDIO_INPUT.value: m.audio_input,
		ModelExtraInfoKey.DOCUMENT_INPUT.value: m.document_input,
		ModelExtraInfoKey.VIDEO_INPUT.value: m.video_input,
		ModelExtraInfoKey.IMAGE_OUTPUT.value: m.image_output,
		ModelExtraInfoKey.AUDIO_OUTPUT.value: m.audio_output,
		ModelExtraInfoKey.VIDEO_OUTPUT.value: m.video_output,
	}


def parse_model_metadata(raw: dict[str, Any]) -> list[ProviderAIModel]:
	"""Parse model-metadata JSON into ProviderAIModel list.

	Extended metadata (modalities beyond vision, supported_parameters, etc.)
	is stored in ``extra_info`` so :class:`ProviderAIModel` stays small.

	Args:
		raw: JSON dict with "models" key containing model objects.

	Returns:
		List of ProviderAIModel instances, sorted by created desc.
	"""
	models: list[ProviderAIModel] = []
	for item in _iter_valid_model_items(raw):
		supported = item.supported_parameters
		architecture = item.architecture
		if not _supports_basilisk_text_output(architecture):
			continue
		modalities = _infer_modality_capabilities(architecture)

		reasoning_capable = _has_reasoning_capable(supported)
		models.append(
			ProviderAIModel(
				id=item.id,
				name=item.name,
				description=item.description,
				context_window=_get_context_length(item.top_provider),
				max_output_tokens=_get_max_completion_tokens(item.top_provider),
				max_temperature=_DEFAULT_MAX_TEMPERATURE_FROM_METADATA,
				default_temperature=_default_temperature(
					item.default_parameters
				),
				vision=modalities.vision,
				reasoning=reasoning_capable,
				created=item.created,
				extra_info={
					ModelExtraInfoKey.SUPPORTED_PARAMETERS.value: supported,
					ModelExtraInfoKey.REASONING_CAPABLE.value: reasoning_capable,
					ModelExtraInfoKey.WEB_SEARCH_CAPABLE.value: _has_web_search_capable(
						item.supports_web_search, supported
					),
					**_extra_info_from_modalities(modalities),
				},
			)
		)

	models.sort(key=lambda m: m.created, reverse=True)
	return models


def _get_cache_ttl_seconds() -> int:
	import basilisk.config as config

	return config.conf().general.model_metadata_cache_ttl_seconds


def load_models_from_url(url: str) -> list[ProviderAIModel]:
	"""Fetch and parse models from URL, with caching."""
	now = time.monotonic()
	ttl = _get_cache_ttl_seconds()
	if url in _CACHE:
		cached_models, cached_at = _CACHE[url]
		if now - cached_at < ttl:
			_LAST_LOAD_ERROR[url] = None
			return cached_models

	try:
		raw = fetch_models_json(url)
		models = parse_model_metadata(raw)
		_CACHE[url] = (models, now)
		_LAST_LOAD_ERROR[url] = None
		log.debug("Loaded %d models from %s", len(models), url)
		return models
	except (httpx.HTTPError, ValueError, TypeError) as e:
		log.warning("Failed to load models from %s: %s", url, e)
		_LAST_LOAD_ERROR[url] = str(e)
		if url in _CACHE:
			return _CACHE[url][0]
		return []


def get_last_load_error(url: str) -> str | None:
	"""Get the most recent load error for a metadata URL."""
	return _LAST_LOAD_ERROR.get(url)
