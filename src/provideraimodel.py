from dataclasses import dataclass, field
from typing import Any


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
	max_temperature: float = field(default=2)
	default_temperature: float = field(default=1)
	vision: bool = field(default=False)
	extra_info: dict[str, Any] = field(default_factory=dict)

	@property
	def display_name(self) -> str:
		return f"{self.name} ({self.id})" if self.name else self.id

	@property
	def display_model(self) -> tuple[str, str, str]:
		return (
			self.display_name,
			str(self.context_window),
			str(self.max_output_tokens),
		)
