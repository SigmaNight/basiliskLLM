from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from .provider_ai_model import ProviderAIModel


class MessageRoleEnum(Enum):
	ASSISTANT = "assistant"
	USER = "user"
	SYSTEM = "system"


class ImageUrlMessageContent(BaseModel):
	type: Literal["image_url"]
	image_url: dict[str, str]


class TextMessageContent(BaseModel):
	type: Literal["text"]
	text: str


class Message(BaseModel):
	role: MessageRoleEnum
	content: list[TextMessageContent | ImageUrlMessageContent] | str = Field(
		discrminator="type"
	)


class MessageBlock(BaseModel):
	request: Message
	response: Message | None = Field(default=None)
	model: ProviderAIModel
	temperature: float = Field(default=1)
	max_tokens: int = Field(default=4096)
	top_p: float = Field(default=1)
	stream: bool = Field(default=False)
	created_at: datetime = Field(default_factory=datetime.now)
	updated_at: datetime = Field(default_factory=datetime.now)


class Conversation(BaseModel):
	system: Message | None = Field(default=None)
	messages: list[MessageBlock] = Field(default_factory=list)
	title: str | None = Field(default=None)


PROMPT_TITLE = "Generate a concise, relevant title in the conversation's main language based on the topics and context. Max 70 characters. Do not surround the text with quotation marks."
