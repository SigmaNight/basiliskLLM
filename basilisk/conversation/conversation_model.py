from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from basilisk.provider_ai_model import ProviderAIModel

from .image_model import ImageFile

PROMPT_TITLE = "Generate a concise, relevant title in the conversation's main language based on the topics and context. Max 70 characters. Do not surround the text with quotation marks."


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
