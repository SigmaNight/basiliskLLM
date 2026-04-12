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
from functools import cached_property
from typing import Annotated

import httpx
from pydantic import (
	BaseModel,
	ConfigDict,
	Field,
	OnErrorOmit,
	StrictStr,
	ValidationError,
	computed_field,
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


class ModalityCapabilities(BaseModel, extra="forbid", frozen=True):
	"""Inferred I/O capabilities for one model (before mapping to ``ProviderAIModel``)."""

	vision: bool
	audio_input: bool
	document_input: bool
	video_input: bool
	image_output: bool
	audio_output: bool
	video_output: bool


class ArchitectureMetadata(BaseModel, extra="ignore"):
	"""Typed architecture metadata used for modality inference."""

	modality: str | None = None
	input_modalities: set[ArchitectureModalityToken] = Field(
		default_factory=set
	)
	output_modalities: set[ArchitectureModalityToken] = Field(
		default_factory=set
	)

	def _extract_io_modalities(self) -> tuple[set[str], set[str]]:
		"""Extract normalized input/output modality tokens from all schema fields."""
		in_str, out_str = _parse_modality_arrow_string(self.modality or "")
		return in_str | set(self.input_modalities), out_str | set(
			self.output_modalities
		)

	def supports_basilisk_text_output(self) -> bool:
		"""Return whether a model can produce text output used by Basilisk UI.

		If output modalities are explicitly provided (either in ``modality`` arrow
		string or ``output_modalities``), require ``text`` to be present.
		When output is not explicit in metadata, assume text output for compatibility.
		"""
		_, output_tokens = self._extract_io_modalities()
		if not output_tokens:
			return True
		return ArchitectureModalityToken.TEXT.value in output_tokens

	@computed_field
	@cached_property
	def modality_capabilities(self) -> ModalityCapabilities:
		"""Derive I/O flags from modality string and modality lists."""
		input_tokens, output_tokens = self._extract_io_modalities()
		return ModalityCapabilities(
			vision=ArchitectureModalityToken.IMAGE in input_tokens,
			audio_input=ArchitectureModalityToken.AUDIO in input_tokens,
			document_input=ArchitectureModalityToken.FILE in input_tokens,
			video_input=ArchitectureModalityToken.VIDEO in input_tokens,
			image_output=ArchitectureModalityToken.IMAGE in output_tokens,
			audio_output=ArchitectureModalityToken.AUDIO in output_tokens,
			video_output=ArchitectureModalityToken.VIDEO in output_tokens,
		)


class TopProviderMetadata(BaseModel, extra="ignore"):
	"""Typed subset of top_provider values used for limits."""

	context_length: int = Field(default=_DEFAULT_CONTEXT_WINDOW)
	max_completion_tokens: int | None = None


class DefaultParametersMetadata(BaseModel):
	"""Typed subset of default_parameters used by Basilisk."""

	model_config = ConfigDict(extra="ignore")

	temperature: float | None = None


class ModelMetadataItem(BaseModel, extra="ignore"):
	"""Validated view of one model row from model-metadata JSON."""

	id: Annotated[StrictStr, Field(min_length=1)]
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

	@model_validator(mode="after")
	def _set_web_search(self) -> ModelMetadataItem:
		if self.supports_web_search is None:
			self.supports_web_search = (
				SupportedApiParameter.TOOLS.value in self.supported_parameters
			)
		return self

	@property
	def has_reasoning_capable(self) -> bool:
		rp = SupportedApiParameter.REASONING.value
		ir = SupportedApiParameter.INCLUDE_REASONING.value
		return (
			rp in self.supported_parameters or ir in self.supported_parameters
		)

	def convert_to_basilisk_model(self) -> ProviderAIModel | None:
		if not self.architecture.supports_basilisk_text_output():
			return None
		modalities = self.architecture.modality_capabilities
		return ProviderAIModel(
			id=self.id,
			name=self.name,
			description=self.description,
			context_window=self.top_provider.context_length,
			max_output_tokens=(
				self.top_provider.max_completion_tokens
				if self.top_provider.max_completion_tokens is not None
				else _DEFAULT_MAX_OUTPUT_TOKENS
			),
			max_temperature=_DEFAULT_MAX_TEMPERATURE_FROM_METADATA,
			default_temperature=(
				self.default_parameters.temperature
				if self.default_parameters.temperature is not None
				else _FALLBACK_DEFAULT_TEMPERATURE
			),
			vision=modalities.vision,
			reasoning=self.has_reasoning_capable,
			created=self.created,
			extra_info={
				ModelExtraInfoKey.SUPPORTED_PARAMETERS.value: self.supported_parameters,
				ModelExtraInfoKey.REASONING_CAPABLE.value: self.has_reasoning_capable,
				ModelExtraInfoKey.WEB_SEARCH_CAPABLE.value: self.supports_web_search,
				**modalities.model_dump(mode="python", exclude={"vision"}),
			},
		)


class ProviderMetadata(BaseModel, extra="ignore"):
	"""Root model for a model-metadata JSON file."""

	models: list[OnErrorOmit[ModelMetadataItem]] = Field(default_factory=list)

	def get_provider_models(self) -> list[ProviderAIModel]:
		"""Convert validated model items to ProviderAIModel list, sorted by created desc.

		Models without text output are excluded. Items that failed Pydantic
		validation were already omitted by ``OnErrorOmit`` during parsing.

		Returns:
			List of ProviderAIModel instances, sorted by created descending.
		"""
		return sorted(
			(
				m
				for m in (x.convert_to_basilisk_model() for x in self.models)
				if m is not None
			),
			key=lambda m: m.created,
			reverse=True,
		)


def fetch_models_json(url: str) -> ProviderMetadata:
	"""Fetch and parse model metadata JSON from URL.

	Args:
		url: URL pointing to a model-metadata JSON file.

	Returns:
		Parsed and validated ``ProviderMetadata`` instance.

	Raises:
		httpx.HTTPError: On request failure.
		ValidationError: If the JSON structure is invalid.
	"""
	response = httpx.get(
		url,
		headers={"User-Agent": f"{APP_NAME} ({APP_SOURCE_URL})"},
		timeout=_HTTP_TIMEOUT_SECONDS,
	)
	response.raise_for_status()
	return ProviderMetadata.model_validate_json(response.text)


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
		provider_metadata = fetch_models_json(url)
		models = provider_metadata.get_provider_models()
		_CACHE[url] = (models, now)
		_LAST_LOAD_ERROR[url] = None
		log.debug("Loaded %d models from %s", len(models), url)
		return models
	except (httpx.HTTPError, ValueError, TypeError, ValidationError) as e:
		log.warning("Failed to load models from %s: %s", url, e)
		_LAST_LOAD_ERROR[url] = str(e)
		if url in _CACHE:
			return _CACHE[url][0]
		return []


def get_last_load_error(url: str) -> str | None:
	"""Get the most recent load error for a metadata URL."""
	return _LAST_LOAD_ERROR.get(url)
