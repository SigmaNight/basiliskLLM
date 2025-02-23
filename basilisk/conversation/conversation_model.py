"""Module for managing conversation between users and the bot."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from upath import UPath

from basilisk.provider_ai_model import AIModelInfo

from .attached_file import AttachmentFile, ImageFile
from .conversation_helper import create_bskc_file, open_bskc_file


class MessageRoleEnum(enum.StrEnum):
	"""Enumeration of the roles that a message can have in a conversation."""

	# The message is from the bot assistant.
	ASSISTANT = enum.auto()
	# The message is from the user.
	USER = enum.auto()
	# The message is a system message.
	SYSTEM = enum.auto()

	@classmethod
	def get_labels(cls) -> dict[MessageRoleEnum, str]:
		"""Get the labels for the different message roles.

		Returns:
			A dictionary mapping each message role to its corresponding translated labels.
		"""
		return {
			# Translators: Label indicating that the message is from the user in a conversation
			cls.USER: _("User:") + ' ',
			# Translators: Label indicating that the message is from the assistant in a conversation
			cls.ASSISTANT: _("Assistant:") + ' ',
			# Translators: Label indicating that the message is a system message in a conversation
			cls.SYSTEM: _("System:") + ' ',
		}


class Message(BaseModel):
	"""Represents a message in a conversation. The message may contain text content and optional attachments."""

	role: MessageRoleEnum
	content: str
	attachments: list[AttachmentFile | ImageFile] | None = Field(default=None)
	citations: list[dict[str, Any]] | None = Field(default=None)


class MessageBlock(BaseModel):
	"""Represents a block of messages in a conversation. The block may contain a user message, an AI model request, and an AI model response."""

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
		"""Validates that a response message does not contain any attachments.

		Args:
		value: The response message to validate.

		Returns:
			The original message if no attachments are present.

		Raises:
			ValueError: If the response message contains attachments.
		"""
		if value and value.attachments:
			raise ValueError("Response messages cannot have attachments.")
		return value

	def __init__(self, /, **data):
		"""Initialize a MessageBlock instance with optional provider and model information.

		This constructor allows flexible initialization of a MessageBlock by automatically
		creating an AIModelInfo instance if provider_id and model_id are provided without
		an existing model.

		Args:
			data: Keyword arguments for MessageBlock initialization
		"""
		provider_id = data.pop("provider_id", None)
		model_id = data.pop("model_id", None)
		model = data.get("model", None)
		if provider_id and model_id and not model:
			data["model"] = AIModelInfo(
				provider_id=provider_id, model_id=model_id
			)
		super().__init__(**data)

	__init__.__pydantic_base_init__ = True

	@model_validator(mode="after")
	def validate_roles(self) -> MessageBlock:
		"""Validates that the roles of the request and response messages are correct.

		Returns:
			The validated MessageBlock instance.

		Raises:
			ValueError: If the roles of the request and response messages are invalid.
		"""
		if self.request.role != MessageRoleEnum.USER:
			raise ValueError("Request message must be from the user.")
		if self.response and self.response.role != MessageRoleEnum.ASSISTANT:
			raise ValueError("Response message must be from the assistant.")
		return self


class Conversation(BaseModel):
	"""Represents a conversation between users and the bot. The conversation may contain messages and a title."""

	system: Message | None = Field(default=None)
	messages: list[MessageBlock] = Field(default_factory=list)
	title: str | None = Field(default=None)

	@classmethod
	def open(cls, file_path: str, base_storage_path: UPath) -> Conversation:
		"""Open a conversation from a file at the specified path.

		Args:
			file_path: The path to the conversation file to be opened.
			base_storage_path: The base storage path for the current conversation file.

		Returns:
			A Conversation instance loaded from the specified file.

		Raises:
			FileNotFoundError: If the specified file does not exist.
			ValueError: If the file cannot be parsed or is invalid.
		"""
		return open_bskc_file(cls, file_path, base_storage_path)

	def save(self, file_path: str):
		"""Save the current conversation to a file.

		Args:
			file_path: The path where the conversation will be saved as a .bskc file.

		Raises:
			IOError: If there is an error writing the file.
			ValueError: If the file path is invalid or cannot be created.
		"""
		create_bskc_file(self, file_path)
