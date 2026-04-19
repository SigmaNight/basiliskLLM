"""Module for loading model metadata from JSON URLs.

Provides reusable fetch and parse logic for providers that use the
model-metadata JSON format (OpenAI, Anthropic, xAI, Mistral, etc.).

Schema reference: https://github.com/SigmaNight/model-metadata — each model
has ``input_modalities`` / ``output_modalities`` arrays that declare the
supported I/O token types (text, image, file, audio, video).
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
	Field,
	OnErrorOmit,
	StrictStr,
	ValidationError,
	computed_field,
)

from basilisk.consts import APP_NAME, APP_SOURCE_URL
from basilisk.decorators import measure_time
from basilisk.provider_ai_model import ProviderAIModel

log = logging.getLogger(__name__)

_CACHE: dict[str, tuple[list[ProviderAIModel], float]] = {}
_LAST_LOAD_ERROR: dict[str, Exception | None] = {}


class ArchitectureModalityToken(StrEnum):
	"""Tokens in modality arrays (lowercase per schema)."""

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

	input_modalities: set[ArchitectureModalityToken] = Field(
		default_factory=set
	)
	output_modalities: set[ArchitectureModalityToken] = Field(
		default_factory=set
	)

	@computed_field
	@cached_property
	def supports_basilisk_text_output(self) -> bool:
		"""Return whether a model can produce text output used by Basilisk UI.

		If output modalities are explicitly provided, require ``text`` to be present.
		When the set is empty (no metadata), assume text output for compatibility.
		"""
		if not self.output_modalities:
			return True
		return ArchitectureModalityToken.TEXT in self.output_modalities

	@computed_field
	@cached_property
	def modality_capabilities(self) -> ModalityCapabilities:
		"""Derive I/O flags directly from the typed modality sets."""
		return ModalityCapabilities(
			vision=ArchitectureModalityToken.IMAGE in self.input_modalities,
			audio_input=ArchitectureModalityToken.AUDIO
			in self.input_modalities,
			document_input=ArchitectureModalityToken.FILE
			in self.input_modalities,
			video_input=ArchitectureModalityToken.VIDEO
			in self.input_modalities,
			image_output=ArchitectureModalityToken.IMAGE
			in self.output_modalities,
			audio_output=ArchitectureModalityToken.AUDIO
			in self.output_modalities,
			video_output=ArchitectureModalityToken.VIDEO
			in self.output_modalities,
		)


class TopProviderMetadata(BaseModel, extra="ignore"):
	"""Typed subset of top_provider values used for limits."""

	context_length: int = Field(default=_DEFAULT_CONTEXT_WINDOW)
	max_completion_tokens: int | None = None


class DefaultParametersMetadata(BaseModel, extra="ignore"):
	"""Typed subset of default_parameters used by Basilisk."""

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

	@computed_field
	@cached_property
	def web_search_capable(self) -> bool:
		"""Derive web search capability from explicit flag or supported_parameters."""
		if self.supports_web_search is not None:
			return self.supports_web_search
		return SupportedApiParameter.TOOLS in self.supported_parameters

	@computed_field
	@cached_property
	def has_reasoning_capable(self) -> bool:
		"""Check whether the model supports reasoning parameters."""
		return (
			SupportedApiParameter.REASONING in self.supported_parameters
			or SupportedApiParameter.INCLUDE_REASONING
			in self.supported_parameters
		)

	def convert_to_basilisk_model(self) -> ProviderAIModel | None:
		"""Convert this metadata item to a ProviderAIModel, or None if not text-capable."""
		if not self.architecture.supports_basilisk_text_output:
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
				ModelExtraInfoKey.WEB_SEARCH_CAPABLE.value: self.web_search_capable,
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


def _get_cache_ttl_seconds() -> int:
	import basilisk.config as config

	return config.conf().general.model_metadata_cache_ttl_seconds


@measure_time
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
	except (httpx.HTTPError, ValidationError, ValueError, TypeError) as e:
		log.warning("Failed to load models from %s: %s", url, e)
		_LAST_LOAD_ERROR[url] = e
		if url in _CACHE:
			return _CACHE[url][0]
		return []


def get_last_load_error(url: str) -> Exception | None:
	"""Get the most recent load error for a metadata URL."""
	return _LAST_LOAD_ERROR.get(url)
