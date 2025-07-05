"""Module for managing conversation between users and the bot."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import (
	BaseModel,
	Field,
	ValidationInfo,
	field_validator,
	model_validator,
)
from upath import UPath

from basilisk.consts import BSKC_VERSION
from basilisk.custom_types import PydanticOrderedSet
from basilisk.provider_ai_model import AIModelInfo

from .attached_file import AttachmentFile, ImageFile
from .conversation_helper import (
	create_bskc_file,
	migration_steps,
	open_bskc_file,
)


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


class BaseMessage(BaseModel):
	"""Base class for messages in a conversation. This class contains common attributes and methods for all message types."""

	role: MessageRoleEnum
	content: str


class Message(BaseMessage):
	"""Represents a message in a conversation. The message may contain text content and optional attachments."""

	attachments: list[AttachmentFile | ImageFile] | None = Field(default=None)
	citations: list[dict[str, Any]] | None = Field(default=None)

	@field_validator("role", mode="after")
	@classmethod
	def validate_role(cls, value: MessageRoleEnum) -> MessageRoleEnum:
		"""Validates that the role of the message is not 'system'.

		Args:
			value: The role of the message to validate.

		Returns:
			The original role value if it is not 'system'.

		Raises:
			ValueError: If the role is 'system'.
		"""
		if value == MessageRoleEnum.SYSTEM:
			raise ValueError("message cannot be system role.")
		return value


class SystemMessage(BaseMessage):
	"""Represents a system message in a conversation. The system message is used to provide instructions or context to the assistant."""

	role: MessageRoleEnum = Field(default=MessageRoleEnum.SYSTEM)

	@field_validator("role", mode="after")
	@classmethod
	def validate_role(cls, value: MessageRoleEnum) -> MessageRoleEnum:
		"""Validates that the role of the system message is 'system'.

		Args:
			value: The role of the message to validate.

		Returns:
			The original role value if it is 'system'.

		Raises:
			ValueError: If the role is not 'system'.
		"""
		if value != MessageRoleEnum.SYSTEM:
			raise ValueError("System messages must have role system.")
		return value

	def __hash__(self):
		"""Compute a hash for the system message based on its content and role.

		Returns:
			Hash value for the system message.
		"""
		return hash((self.role, self.content))


class MessageBlock(BaseModel):
	"""Represents a block of messages in a conversation. The block may contain a user message, an AI model request, and an AI model response."""

	request: Message
	response: Message | None = Field(default=None)
	system_index: int | None = Field(default=None, ge=0)
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

	messages: list[MessageBlock] = Field(default_factory=list)
	systems: PydanticOrderedSet[SystemMessage] = Field(
		default_factory=PydanticOrderedSet
	)
	title: str | None = Field(default=None)
	version: int = Field(default=BSKC_VERSION, ge=0, le=BSKC_VERSION)

	@model_validator(mode="before")
	@classmethod
	def migrate_bskc_version(
		cls, value: Any, info: ValidationInfo
	) -> dict[str, Any]:
		"""Migrates the conversation to the latest BSKC version if necessary.

		Args:
			value: The value to migrate.
			info: Validation information.

		Returns:
			The conversation dict updated after migration.

		Raises:
			ValueError: If the version is invalid
		"""
		if not isinstance(value, dict):
			raise ValueError("Invalid conversation format")
		version = value.get("version", 0)
		if version < 0 or version > BSKC_VERSION:
			raise ValueError("Invalid conversation version")
		while version < BSKC_VERSION:
			migration_func = migration_steps[version]
			value = migration_func(value, info)
			version += 1
		value["version"] = version
		return value

	@model_validator(mode="after")
	def validate_system_indexes(self) -> Conversation:
		"""Validates that all system indexes in the messages are valid.

		Returns:
			The validated Conversation instance.

		Raises:
			ValueError: If any system index in the messages is invalid.
		"""
		systems_length = len(self.systems)
		for message in self.messages:
			index = message.system_index
			if index is not None and index >= systems_length:
				raise ValueError("Invalid system index")
		return self

	def add_block(
		self, block: MessageBlock, system: SystemMessage | None = None
	):
		"""Adds a message block to the conversation.

		Args:
			block: The message block to be added to the conversation.
			system: The system message to be added to the conversation.
		"""
		if system:
			index = self.systems.add(system)
			block.system_index = index
		self.messages.append(block)

	def remove_block(self, block: MessageBlock) -> None:
		"""Removes a message block from the conversation and manages system messages.

		If a system message is not referenced by any block after removal,
		the system message will also be removed.

		Args:
			block: The message block to be removed from the conversation.

		Raises:
			ValueError: If the block is not found in the conversation.
		"""
		system_index = block.system_index
		self.messages.remove(block)
		if system_index is not None:
			self._remove_orphaned_system(system_index)

	def _remove_orphaned_system(self, system_index: int) -> None:
		"""Removes a system message from the conversation if it is not referenced by any block.

		Args:
			system_index: The index of the system message to remove.
		"""
		is_referenced = any(
			b.system_index == system_index for b in self.messages
		)
		if not is_referenced:
			system_to_remove = self.systems[system_index]
			self.systems.discard(system_to_remove)
			for block in self.messages:
				if block.system_index > system_index:
					block.system_index -= 1

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
