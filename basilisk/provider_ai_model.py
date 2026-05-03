"""Structures for catalog AI models and lightweight export model references."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .provider import Provider, get_provider


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
		from basilisk.model_catalog.display import (
			build_provider_model_display_details,
		)

		return build_provider_model_display_details(self)

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
