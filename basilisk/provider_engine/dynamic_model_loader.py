"""Module for loading model metadata from JSON URLs.

Provides reusable fetch and parse logic for providers that use the
model-metadata JSON format (OpenAI, Anthropic, xAI, Mistral, etc.).

Schema reference: https://github.com/SigmaNight/model-metadata — each model
has ``input_modalities`` / ``output_modalities`` arrays that declare the
supported I/O token types (text, image, file, audio, video).
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import StrEnum, auto
from functools import cached_property
from typing import Annotated, Any

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
from basilisk.model_catalog.display import summarize_pricing
from basilisk.model_catalog.sampling import METADATA_CATALOG_EXTRA_KEY
from basilisk.provider_ai_model import ProviderAIModel

log = logging.getLogger(__name__)

CATALOG_SOURCE_SIGMA_NIGHT_MASTER = "sigma_night/master"
CATALOG_SOURCE_OPENROUTER_API = "openrouter/api"


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
	UNSUPPORTED_PARAMETERS = auto()
	REASONING_CAPABLE = auto()
	WEB_SEARCH_CAPABLE = auto()
	AUDIO_INPUT = auto()
	DOCUMENT_INPUT = auto()
	VIDEO_INPUT = auto()
	IMAGE_OUTPUT = auto()
	AUDIO_OUTPUT = auto()
	VIDEO_OUTPUT = auto()


_HTTP_TIMEOUT_SECONDS = 30.0
_DEFAULT_MAX_TEMPERATURE_FROM_METADATA = 2.0
_FALLBACK_DEFAULT_TEMPERATURE = 1.0
_DEFAULT_CONTEXT_WINDOW = 0
_DEFAULT_MAX_OUTPUT_TOKENS = -1
_INPUT_MODALITY_INDEX = 0
_OUTPUT_MODALITY_INDEX = 1


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
	modality: str | None = None
	tokenizer: str | None = None
	instruct_type: str | None = None

	@staticmethod
	def _split_modality_tokens(
		modality: str | None, side: int
	) -> set[ArchitectureModalityToken]:
		"""Extract typed modality tokens from ``modality`` string side."""
		if not modality:
			return set()
		parts = modality.split("->", maxsplit=1)
		if side >= len(parts):
			return set()
		tokens: set[ArchitectureModalityToken] = set()
		for raw in parts[side].split("+"):
			token = raw.strip().lower()
			if not token:
				continue
			try:
				tokens.add(ArchitectureModalityToken(token))
			except ValueError:
				continue
		return tokens

	@computed_field
	@cached_property
	def inferred_input_modalities(self) -> set[ArchitectureModalityToken]:
		"""Return input modality tokens, falling back to ``modality``."""
		if self.input_modalities:
			return self.input_modalities
		return self._split_modality_tokens(self.modality, _INPUT_MODALITY_INDEX)

	@computed_field
	@cached_property
	def inferred_output_modalities(self) -> set[ArchitectureModalityToken]:
		"""Return output modality tokens, falling back to ``modality``."""
		if self.output_modalities:
			return self.output_modalities
		return self._split_modality_tokens(
			self.modality, _OUTPUT_MODALITY_INDEX
		)

	@computed_field
	@cached_property
	def supports_basilisk_text_output(self) -> bool:
		"""Return whether a model can produce text output used by Basilisk UI.

		If output modalities are explicitly provided, require ``text`` to be present.
		When the set is empty (no metadata), assume text output for compatibility.
		"""
		modalities = self.inferred_output_modalities
		if not modalities:
			return True
		return ArchitectureModalityToken.TEXT in modalities

	@computed_field
	@cached_property
	def modality_capabilities(self) -> ModalityCapabilities:
		"""Derive I/O flags directly from the typed modality sets."""
		input_modalities = self.inferred_input_modalities
		output_modalities = self.inferred_output_modalities
		return ModalityCapabilities(
			vision=ArchitectureModalityToken.IMAGE in input_modalities,
			audio_input=ArchitectureModalityToken.AUDIO in input_modalities,
			document_input=ArchitectureModalityToken.FILE in input_modalities,
			video_input=ArchitectureModalityToken.VIDEO in input_modalities,
			image_output=ArchitectureModalityToken.IMAGE in output_modalities,
			audio_output=ArchitectureModalityToken.AUDIO in output_modalities,
			video_output=ArchitectureModalityToken.VIDEO in output_modalities,
		)


class TopProviderMetadata(BaseModel, extra="ignore"):
	"""Typed subset of top_provider values used for limits."""

	context_length: int | None = None
	max_completion_tokens: int | None = None
	is_moderated: bool | None = None


class DefaultParametersMetadata(BaseModel, extra="ignore"):
	"""Typed subset of default_parameters used by Basilisk."""

	temperature: float | None = None


class ModelMetadataItem(BaseModel, extra="ignore"):
	"""Validated view of one model row from model-metadata JSON."""

	id: Annotated[StrictStr, Field(min_length=1)]
	name: str | None = None
	description: str | None = None
	created: int | str | None = 0
	context_length: int | None = None
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
	unsupported_parameters: list[str] = Field(default_factory=list)
	supports_web_search: bool | None = None
	pricing: dict[str, str | int | float | None] = Field(default_factory=dict)

	@computed_field
	@cached_property
	def created_timestamp(self) -> int:
		"""Return normalized created timestamp (int, fallback 0)."""
		return parse_created_timestamp(self.created)

	@computed_field
	@cached_property
	def resolved_context_length(self) -> int:
		"""Prefer ``top_provider.context_length``, fallback to root value."""
		if self.top_provider.context_length is not None:
			return self.top_provider.context_length
		if self.context_length is not None:
			return self.context_length
		return _DEFAULT_CONTEXT_WINDOW

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

	def convert_to_basilisk_model(
		self, catalog_source: str = CATALOG_SOURCE_SIGMA_NIGHT_MASTER
	) -> ProviderAIModel | None:
		"""Convert this metadata item to a ProviderAIModel, or None if not text-capable.

		Args:
			catalog_source: Stored in ``extra_info`` so UI and completion policy
				know which catalog produced this row (SigmaNight vs OpenRouter API).
		"""
		if not self.architecture.supports_basilisk_text_output:
			return None
		modalities = self.architecture.modality_capabilities
		pricing_summary = summarize_pricing(self.pricing)
		extra_info = {
			METADATA_CATALOG_EXTRA_KEY: catalog_source,
			ModelExtraInfoKey.SUPPORTED_PARAMETERS.value: self.supported_parameters,
			ModelExtraInfoKey.UNSUPPORTED_PARAMETERS.value: list(
				self.unsupported_parameters
			),
			ModelExtraInfoKey.REASONING_CAPABLE.value: self.has_reasoning_capable,
			ModelExtraInfoKey.WEB_SEARCH_CAPABLE.value: self.web_search_capable,
			**modalities.model_dump(mode="python", exclude={"vision"}),
		}
		if pricing_summary:
			extra_info["Pricing"] = pricing_summary
		if self.created_timestamp:
			try:
				extra_info["created"] = datetime.fromtimestamp(
					self.created_timestamp
				).strftime("%Y-%m-%d %H:%M:%S")
			except (OSError, OverflowError, ValueError) as exc:
				log.debug(
					"Skipping extra_info created for model %s (timestamp=%r): %s",
					self.id,
					self.created_timestamp,
					exc,
				)
		in_mod = self.architecture.inferred_input_modalities
		out_mod = self.architecture.inferred_output_modalities
		if in_mod:
			extra_info["input_modalities"] = ", ".join(
				sorted(t.value for t in in_mod)
			)
		if out_mod:
			extra_info["output_modalities"] = ", ".join(
				sorted(t.value for t in out_mod)
			)
		if self.architecture.modality:
			extra_info["modality_route"] = self.architecture.modality
		if self.architecture.tokenizer:
			extra_info["tokenizer"] = self.architecture.tokenizer
		if self.architecture.instruct_type is not None:
			extra_info["instruct_type"] = str(self.architecture.instruct_type)
		if self.top_provider.is_moderated is not None:
			extra_info["is_moderated"] = self.top_provider.is_moderated
		return ProviderAIModel(
			id=self.id,
			name=self.name,
			description=self.description,
			context_window=self.resolved_context_length,
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
			created=self.created_timestamp,
			extra_info=extra_info,
		)


class ProviderMetadata(BaseModel, extra="ignore"):
	"""Root model for a model-metadata JSON file."""

	models: list[OnErrorOmit[ModelMetadataItem]] = Field(default_factory=list)

	def get_provider_models(
		self, catalog_source: str = CATALOG_SOURCE_SIGMA_NIGHT_MASTER
	) -> list[ProviderAIModel]:
		"""Convert validated model items to ProviderAIModel list, sorted by created desc.

		Models without text output are excluded. Items that failed Pydantic
		validation were already omitted by ``OnErrorOmit`` during parsing.

		Args:
			catalog_source: Label written to each model's ``extra_info``.

		Returns:
			List of ProviderAIModel instances, sorted by created descending.
		"""
		return sorted(
			(
				m
				for m in (
					x.convert_to_basilisk_model(catalog_source=catalog_source)
					for x in self.models
				)
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


def parse_model_rows(rows: list[Any]) -> list[ProviderAIModel]:
	"""Convert raw model rows into ProviderAIModel list (e.g. OpenRouter API)."""
	return ProviderMetadata.model_validate(
		{"models": rows}
	).get_provider_models(catalog_source=CATALOG_SOURCE_OPENROUTER_API)


def parse_created_timestamp(value: Any) -> int:
	"""Return ``created`` value as int timestamp, fallback to 0."""
	try:
		return int(value)
	except TypeError, ValueError:
		return 0


@measure_time
def load_models_from_url(url: str) -> list[ProviderAIModel]:
	"""Fetch and parse models from URL without engine-level caching."""
	try:
		provider_metadata = fetch_models_json(url)
		models = provider_metadata.get_provider_models(
			catalog_source=CATALOG_SOURCE_SIGMA_NIGHT_MASTER
		)
		log.debug("Loaded %d models from %s", len(models), url)
		return models
	except (httpx.HTTPError, ValidationError, ValueError, TypeError) as e:
		log.warning("Failed to load models from %s: %s", url, e)
		raise
