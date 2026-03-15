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
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any

import httpx

from basilisk.consts import APP_NAME, APP_SOURCE_URL
from basilisk.provider_ai_model import ProviderAIModel

log = logging.getLogger(__name__)

_CACHE: dict[str, tuple[list[ProviderAIModel], float]] = {}


class ModelMetadataField(StrEnum):
	"""Field names used in model-metadata JSON objects.

	Values match schema keys (``StrEnum`` + ``auto()`` lowercases member names).
	"""

	MODELS = auto()
	ID = auto()
	NAME = auto()
	DESCRIPTION = auto()
	CREATED = auto()
	ARCHITECTURE = auto()
	MODALITY = auto()
	INPUT_MODALITIES = auto()
	OUTPUT_MODALITIES = auto()
	TOP_PROVIDER = auto()
	CONTEXT_LENGTH = auto()
	MAX_COMPLETION_TOKENS = auto()
	DEFAULT_PARAMETERS = auto()
	TEMPERATURE = auto()
	SUPPORTED_PARAMETERS = auto()
	SUPPORTS_WEB_SEARCH = auto()


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


@dataclass(frozen=True, slots=True)
class ModalityCapabilities:
	"""Inferred I/O capabilities for one model (before mapping to ``ProviderAIModel``)."""

	vision: bool
	audio_input: bool
	document_input: bool
	video_input: bool
	image_output: bool
	audio_output: bool
	video_output: bool


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


def _get_int_from_top_provider(
	model: dict[str, Any], field: ModelMetadataField, default: int
) -> int:
	"""Extract an integer from ``top_provider`` with a default fallback."""
	top = model.get(ModelMetadataField.TOP_PROVIDER)
	if not top or not isinstance(top, dict):
		return default
	val = top.get(field)
	if val is None:
		return default
	try:
		return int(val)
	except TypeError, ValueError:
		return default


def _get_max_completion_tokens(model: dict[str, Any]) -> int:
	"""Extract max_completion_tokens from top_provider, or -1 if absent."""
	return _get_int_from_top_provider(
		model,
		ModelMetadataField.MAX_COMPLETION_TOKENS,
		_DEFAULT_MAX_OUTPUT_TOKENS,
	)


def _get_context_length(model: dict[str, Any]) -> int:
	"""Extract context_length from top_provider only (no top-level fallback)."""
	return _get_int_from_top_provider(
		model, ModelMetadataField.CONTEXT_LENGTH, _DEFAULT_CONTEXT_WINDOW
	)


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
	architecture: dict[str, Any],
) -> tuple[set[str], set[str]]:
	"""Extract normalized input/output modality tokens from all schema fields."""
	raw_modality = architecture.get(ModelMetadataField.MODALITY)
	in_str, out_str = _parse_modality_arrow_string(
		str(raw_modality) if raw_modality is not None else ""
	)
	input_mods = _normalize_modalities_list(
		architecture.get(ModelMetadataField.INPUT_MODALITIES)
	)
	output_mods = _normalize_modalities_list(
		architecture.get(ModelMetadataField.OUTPUT_MODALITIES)
	)
	return in_str | input_mods, out_str | output_mods


def _infer_modality_capabilities(
	architecture: dict[str, Any],
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


def _supports_basilisk_text_output(architecture: dict[str, Any]) -> bool:
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


def _has_web_search_capable(item: dict[str, Any], supported: list[str]) -> bool:
	explicit = item.get(ModelMetadataField.SUPPORTS_WEB_SEARCH)
	if explicit is True:
		return True
	if explicit is False:
		return False
	return SupportedApiParameter.TOOLS.value in supported


def _get_created(model: dict[str, Any]) -> int:
	val = model.get(ModelMetadataField.CREATED)
	if val is None:
		return 0
	try:
		return int(val)
	except TypeError, ValueError:
		return 0


def _default_temperature(item: dict[str, Any]) -> float:
	"""Use numeric ``default_parameters.temperature`` when present."""
	dp = item.get(ModelMetadataField.DEFAULT_PARAMETERS)
	if not isinstance(dp, dict):
		return _FALLBACK_DEFAULT_TEMPERATURE
	t = dp.get(ModelMetadataField.TEMPERATURE)
	if isinstance(t, bool):
		return _FALLBACK_DEFAULT_TEMPERATURE
	if isinstance(t, (int, float)):
		return float(t)
	return _FALLBACK_DEFAULT_TEMPERATURE


def _supported_parameters(item: dict[str, Any]) -> list[str]:
	"""Normalize ``supported_parameters`` to a list of strings."""
	supported = item.get(ModelMetadataField.SUPPORTED_PARAMETERS)
	if not isinstance(supported, list):
		return []
	return [str(s) for s in supported]


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
	model_list = raw.get(ModelMetadataField.MODELS)
	if not isinstance(model_list, list):
		return models

	for item in model_list:
		if not isinstance(item, dict):
			continue
		model_id = item.get(ModelMetadataField.ID)
		if not model_id or not isinstance(model_id, str):
			continue

		supported = _supported_parameters(item)

		architecture = item.get(ModelMetadataField.ARCHITECTURE) or {}
		if not isinstance(architecture, dict):
			architecture = {}
		if not _supports_basilisk_text_output(architecture):
			continue
		modalities = _infer_modality_capabilities(architecture)

		reasoning_capable = _has_reasoning_capable(supported)
		models.append(
			ProviderAIModel(
				id=model_id,
				name=item.get(ModelMetadataField.NAME),
				description=item.get(ModelMetadataField.DESCRIPTION),
				context_window=_get_context_length(item),
				max_output_tokens=_get_max_completion_tokens(item),
				max_temperature=_DEFAULT_MAX_TEMPERATURE_FROM_METADATA,
				default_temperature=_default_temperature(item),
				vision=modalities.vision,
				reasoning=reasoning_capable,
				created=_get_created(item),
				extra_info={
					ModelExtraInfoKey.SUPPORTED_PARAMETERS.value: supported,
					ModelExtraInfoKey.REASONING_CAPABLE.value: reasoning_capable,
					ModelExtraInfoKey.WEB_SEARCH_CAPABLE.value: _has_web_search_capable(
						item, supported
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
			return cached_models

	try:
		raw = fetch_models_json(url)
		models = parse_model_metadata(raw)
		_CACHE[url] = (models, now)
		log.debug("Loaded %d models from %s", len(models), url)
		return models
	except (httpx.HTTPError, ValueError, TypeError) as e:
		log.warning("Failed to load models from %s: %s", url, e)
		if url in _CACHE:
			return _CACHE[url][0]
		return []
