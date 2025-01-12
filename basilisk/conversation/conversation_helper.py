from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
	from basilisk.provider import Provider

PROMPT_TITLE = "Generate a concise, relevant title in the conversation's main language based on the topics and context. Max 70 characters. Do not surround the text with quotation marks."


class AIModelInfo(BaseModel):
	provider_id: str = Field(pattern=r"^[a-zA-Z]+$")
	model_id: str = Field(pattern=r"^.+$")

	@staticmethod
	def get_provider_by_id(provider_id: str) -> Provider:
		from basilisk.provider import get_provider

		return get_provider(id=provider_id)

	@field_validator("provider_id", mode="after")
	@classmethod
	def provider_must_exist(cls, value: str) -> str:
		return cls.get_provider_by_id(value)

	@property
	def provider(self) -> Provider:
		return self.get_provider_by_id(self.provider_id)
