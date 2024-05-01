from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class MessageRoleEnum(Enum):
	ASSISTANT = "assistant"
	USER = "user"
	SYSTEM = "system"


class TextMessageConten(BaseModel):
	type: Literal["text"]
	text: str


class ImageUrlMessageContent(BaseModel):
	type: Literal["image_url"]
	image_url: dict[str, str]


class Message(BaseModel):
	role: MessageRoleEnum
	content: list[TextMessageConten | ImageUrlMessageContent] | str = Field(
		discrminator="type"
	)
	date: datetime


class MessageBlock(BaseModel):
	request: Message
	response: Message
	temperature: float = Field(default=1)


class SystemMessageBlock(BaseModel):
	message: Message
	start_block: int = Field(default=0)
	end_block: int = Field(default=-1)


class Conversation(BaseModel):
	systems: list[SystemMessageBlock]
	messages: list[MessageBlock]
