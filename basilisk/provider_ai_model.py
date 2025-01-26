from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .provider import Provider, get_provider


@dataclass
class ProviderAIModel:
	"""
	Provider AI Model
	"""

	id: str
	name: str | None = field(default=None)
	description: str | None = field(default=None)
	context_window: int = field(default=0)
	max_output_tokens: int = field(default=-1)
	max_temperature: float = field(default=1.0)
	default_temperature: float = field(default=1.0)
	vision: bool = field(default=False)
	extra_info: dict[str, Any] = field(default_factory=dict)

	@property
	def display_name(self) -> str:
		return f"{self.name} ({self.id})" if self.name else self.id

	@property
	def display_model(self) -> tuple[str, str, str]:
		return (
			self.display_name,
			_("yes") if self.vision else _("no"),
			str(self.context_window),
			str(self.max_output_tokens) if self.max_output_tokens > 0 else "",
		)

	@property
	def display_details(self) -> str:
		details = f"{self.display_name}\n"
		vision_value = _("yes") if self.vision else _("no")
		# translator: AI model details
		details += _("Vision:") + f" {vision_value}\n"
		# translator: AI model details
		details += _("Context window:") + f" {self.context_window}\n"
		if self.max_output_tokens > 0:
			# translator: AI model details
			details += _("Max output tokens:") + f" {self.max_output_tokens}\n"
		details += f"\n```\n{self.description}\n```"
		if self.extra_info:
			details += "\n\n" + "\n".join(
				f"{k}: {v}" for k, v in self.extra_info.items()
			)
		return details

	@property
	def effective_max_output_tokens(self) -> int:
		"""
		Calculates the effective maximum number of output tokens for the AI model.
		
		Returns the maximum output tokens based on the following logic:
		- If `max_output_tokens` is negative, returns the model's context window size
		- Otherwise, returns the explicitly set `max_output_tokens`
		
		Returns:
		    int: The effective maximum number of output tokens
		"""
		if self.max_output_tokens < 0:
			return self.context_window
		return self.max_output_tokens


class AIModelInfo(BaseModel):
	provider_id: str = Field(pattern=r"^[a-zA-Z]+$")
	model_id: str = Field(pattern=r"^.+$")

	@staticmethod
	def get_provider_by_id(provider_id: str) -> Provider:
		"""
		Retrieve a provider instance by its unique identifier.
		
		Parameters:
		    provider_id (str): The unique identifier of the provider to retrieve.
		
		Returns:
		    Provider: The provider instance corresponding to the given provider ID.
		
		Raises:
		    ValueError: If no provider is found with the specified ID.
		"""
		return get_provider(id=provider_id)

	@field_validator("provider_id", mode="after")
	@classmethod
	def provider_must_exist(cls, value: str) -> str:
		"""
		Validates that a provider exists for the given provider ID.
		
		This class method checks the existence of a provider by attempting to retrieve it using the provided ID.
		If the provider is not found, a validation error will be raised.
		
		Parameters:
		    value (str): The provider ID to validate.
		
		Returns:
		    str: The original provider ID if a valid provider is found.
		
		Raises:
		    ValueError: If no provider is found for the given provider ID.
		"""
		cls.get_provider_by_id(value)
		return value

	@property
	def provider(self) -> Provider:
		"""
		Retrieves the Provider instance associated with the current model's provider ID.
		
		Returns:
		    Provider: The Provider instance corresponding to the model's provider_id.
		
		Raises:
		    ValueError: If no Provider is found for the given provider_id.
		"""
		return self.get_provider_by_id(self.provider_id)
