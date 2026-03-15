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


class TokenUsage(BaseModel):
	"""Token consumption for a completion request.

	Normalized across providers. All fields optional except where noted.
	"""

	input_tokens: int = 0
	output_tokens: int = 0
	reasoning_tokens: int | None = None
	cached_input_tokens: int | None = None
	cache_write_tokens: int | None = (
		None  # Tokens written to cache (different pricing)
	)
	audio_tokens: int | None = None  # Audio input tokens
	total_tokens: int | None = None
	cost: float | None = (
		None  # Provider-reported cost (e.g. OpenRouter usage.cost)
	)

	@property
	def effective_total(self) -> int:
		"""Total tokens (computed if not provided)."""
		if self.total_tokens is not None:
			return self.total_tokens
		return self.input_tokens + self.output_tokens


class ResponseTiming(BaseModel):
	"""Timing for a completion request."""

	started_at: datetime | None = None
	request_sent_at: datetime | None = None
	first_token_at: datetime | None = None
	finished_at: datetime | None = None

	@property
	def duration_seconds(self) -> float | None:
		"""Total duration in seconds (start to last token), or None if incomplete."""
		if self.started_at is None or self.finished_at is None:
			return None
		return (self.finished_at - self.started_at).total_seconds()

	@property
	def time_to_send_request_seconds(self) -> float | None:
		"""Time from start until request fully sent. None if request_sent_at unknown."""
		if (
			self.started_at is None
			or self.request_sent_at is None
			or self.request_sent_at < self.started_at
		):
			return None
		return (self.request_sent_at - self.started_at).total_seconds()

	@property
	def time_to_first_token_seconds(self) -> float | None:
		"""Time from request sent to first token received (TTFT). None if unknown."""
		# Use request_sent_at when available, else started_at for backward compat
		from_ts = (
			self.request_sent_at
			if self.request_sent_at is not None
			else self.started_at
		)
		if (
			from_ts is None
			or self.first_token_at is None
			or self.first_token_at < from_ts
		):
			return None
		return (self.first_token_at - from_ts).total_seconds()

	@property
	def generation_duration_seconds(self) -> float | None:
		"""Time from first token to last token (excludes TTFT). None if first_token_at unknown."""
		if (
			self.first_token_at is None
			or self.finished_at is None
			or self.finished_at < self.first_token_at
		):
			return None
		return (self.finished_at - self.first_token_at).total_seconds()


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
			cls.USER: _("User:") + " ",
			# Translators: Label indicating that the message is from the assistant in a conversation
			cls.ASSISTANT: _("Assistant:") + " ",
			# Translators: Label indicating that the message is a system message in a conversation
			cls.SYSTEM: _("System:") + " ",
		}


class BaseMessage(BaseModel):
	"""Base class for messages in a conversation. This class contains common attributes and methods for all message types."""

	role: MessageRoleEnum
	content: str


class Message(BaseMessage):
	"""Represents a message in a conversation. The message may contain text content and optional attachments."""

	reasoning: str | None = Field(default=None)
	attachments: list[AttachmentFile | ImageFile] | None = Field(default=None)
	citations: list[dict[str, Any]] | None = Field(default=None)
	reasoning: str | None = Field(default=None)

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
	db_id: int | None = Field(default=None, exclude=True)

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

	def __eq__(self, other: object) -> bool:
		"""Compare system messages by role and content, ignoring db_id.

		Args:
			other: The object to compare against.

		Returns:
			True if role and content match, False otherwise.
		"""
		if not isinstance(other, SystemMessage):
			return NotImplemented
		return self.role == other.role and self.content == other.content


class MessageBlock(BaseModel):
	"""Represents a block of messages in a conversation. The block may contain a user message, an AI model request, and an AI model response."""

	request: Message
	response: Message | None = Field(default=None)
	system_index: int | None = Field(default=None, ge=0)
	model: AIModelInfo
	temperature: float = Field(default=1)
	max_tokens: int = Field(default=4096)
	top_p: float = Field(default=1)
	frequency_penalty: float = Field(default=0)
	presence_penalty: float = Field(default=0)
	seed: int | None = Field(default=None)
	top_k: int | None = Field(default=None)
	stop: list[str] | None = Field(default=None)
	stream: bool = Field(default=False)
	reasoning_mode: bool = Field(default=False)
	reasoning_budget_tokens: int | None = Field(default=None)
	reasoning_effort: str | None = Field(default=None)
	reasoning_adaptive: bool = Field(default=False)
	web_search_mode: bool = Field(default=False)
	output_modality: str = Field(default="text")
	audio_voice: str = Field(default="alloy")
	audio_format: str = Field(default="wav")
	created_at: datetime = Field(default_factory=datetime.now)
	updated_at: datetime = Field(default_factory=datetime.now)
	db_id: int | None = Field(default=None, exclude=True)
	usage: TokenUsage | None = Field(default=None)
	timing: ResponseTiming | None = Field(default=None)
	cost: float | None = Field(
		default=None
	)  # Block cost in USD (from provider or computed)
	cost_breakdown: dict[str, float] | None = Field(
		default=None
	)  # Per-token-type cost for display (input, output, reasoning, cached, cache_write, audio, etc.)

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
	# model_id -> field -> ISO datetime -> price (USD per token)
	pricing_snapshot: dict[str, dict[str, dict[str, float]]] = Field(
		default_factory=dict
	)

	# --- Conversation-level computed properties ---

	@property
	def token_total(self) -> int:
		"""Total tokens consumed across all message blocks (input + output)."""
		total = 0
		for block in self.messages:
			if block.usage:
				total += block.usage.effective_total
		return total

	@property
	def input_tokens_total(self) -> int:
		"""Total input tokens across all blocks."""
		return sum(b.usage.input_tokens for b in self.messages if b.usage)

	@property
	def output_tokens_total(self) -> int:
		"""Total output tokens across all blocks."""
		return sum(b.usage.output_tokens for b in self.messages if b.usage)

	@property
	def reasoning_tokens_total(self) -> int:
		"""Total reasoning tokens across all blocks."""
		return sum(
			b.usage.reasoning_tokens or 0 for b in self.messages if b.usage
		)

	@property
	def cached_input_tokens_total(self) -> int:
		"""Total cached input tokens across all blocks."""
		return sum(
			b.usage.cached_input_tokens or 0 for b in self.messages if b.usage
		)

	@property
	def total_duration_seconds(self) -> float | None:
		"""Total duration from first block start to last block finish (if timing available)."""
		if not self.messages:
			return None
		starts: list[datetime] = []
		ends: list[datetime] = []
		for block in self.messages:
			if block.timing:
				if block.timing.started_at:
					starts.append(block.timing.started_at)
				if block.timing.finished_at:
					ends.append(block.timing.finished_at)
		if not starts or not ends:
			return None
		return (max(ends) - min(starts)).total_seconds()

	@property
	def average_tokens_per_block(self) -> float | None:
		"""Average tokens per block (token_total / block_count). None if no blocks."""
		if not self.messages:
			return None
		return self.token_total / len(self.messages)

	@property
	def started_at(self) -> datetime | None:
		"""Start date of the conversation (first block's created_at)."""
		if not self.messages:
			return None
		return min(b.created_at for b in self.messages)

	@property
	def last_activity_at(self) -> datetime | None:
		"""Last activity date (most recent block's updated_at)."""
		if not self.messages:
			return None
		return max(b.updated_at for b in self.messages)

	@property
	def block_count(self) -> int:
		"""Number of message blocks (request/response pairs)."""
		return len(self.messages)

	@property
	def models_used(self) -> list[str]:
		"""List of unique model identifiers used in the conversation."""
		seen: set[str] = set()
		result: list[str] = []
		for block in self.messages:
			key = f"{block.model.provider_id}/{block.model.model_id}"
			if key not in seen:
				seen.add(key)
				result.append(key)
		return result

	@property
	def cache_write_tokens_total(self) -> int:
		"""Total cache write tokens across all blocks."""
		return sum(
			b.usage.cache_write_tokens or 0 for b in self.messages if b.usage
		)

	@property
	def audio_tokens_total(self) -> int:
		"""Total audio tokens across all blocks."""
		return sum(b.usage.audio_tokens or 0 for b in self.messages if b.usage)

	@property
	def cost_total(self) -> float | None:
		"""Total cost across blocks (from block.cost or usage.cost)."""
		costs: list[float] = []
		for block in self.messages:
			c = (
				block.cost
				if block.cost is not None
				else (
					block.usage.cost
					if block.usage and block.usage.cost is not None
					else None
				)
			)
			if c is not None:
				costs.append(c)
		if not costs:
			return None
		return sum(costs)

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
