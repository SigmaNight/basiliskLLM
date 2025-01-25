from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from .conversation_helper import AIModelInfo, create_bskc_file, open_bskc_file
from .image_model import ImageFile


class MessageRoleEnum(Enum):
	ASSISTANT = "assistant"
	USER = "user"
	SYSTEM = "system"


class Message(BaseModel):
	role: MessageRoleEnum
	content: str
	attachments: list[ImageFile] | None = Field(default=None)


class MessageBlock(BaseModel):
	request: Message
	response: Message | None = Field(default=None)
	model: AIModelInfo
	temperature: float = Field(default=1)
	max_tokens: int = Field(default=4096)
	top_p: float = Field(default=1)
	stream: bool = Field(default=False)
	created_at: datetime = Field(default_factory=datetime.now)
	updated_at: datetime = Field(default_factory=datetime.now)

	@field_validator("response", mode="after")
	@classmethod
	def no_attachment_in_response(cls, value: Message | None) -> Message | None:
		if value and value.attachments:
			raise ValueError("Response messages cannot have attachments.")
		return value

	def __init__(self, /, **data):
		provider_id = data.pop("provider_id", None)
		model_id = data.pop("model_id", None)
		model = data.get("model", None)
		if provider_id and model_id and not model:
			data["model"] = AIModelInfo(
				provider_id=provider_id, model_id=model_id
			)
		super().__init__(**data)


class Conversation(BaseModel):
	system: Message | None = Field(default=None)
	messages: list[MessageBlock] = Field(default_factory=list)
	title: str | None = Field(default=None)

	@classmethod
	def open(cls, file_path: str) -> Conversation:
		return open_bskc_file(cls, file_path)

	def save(self, file_path: str):
		create_bskc_file(self, file_path)
