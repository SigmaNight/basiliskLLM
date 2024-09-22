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
		details = (
			f"{self.display_name}\n"
			f"{_('Vision')}: {'yes' if self.vision else 'no'}\n"
			f"{_('Context window')}: {self.context_window}\n"
		)
		if self.max_output_tokens > 0:
			details += f"{_('Max output tokens')}: {self.max_output_tokens}\n\n"

		details += self.description
		if self.extra_info:
			details += "\n\n" + "\n".join(
				f"{k}: {v}" for k, v in self.extra_info.items()
			)
		return details
