"""Base module for AI provider engines.

This module defines the abstract base class for all AI provider engines,
establishing the common interface and shared functionality.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Any, Optional

from basilisk.consts import APP_NAME, APP_SOURCE_URL
from basilisk.conversation import Conversation, Message, MessageBlock
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

if TYPE_CHECKING:
	from basilisk.config import Account


class BaseEngine(ABC):
	"""Abstract base class for AI provider engines.

	Defines the interface that all provider-specific engines must implement,
	providing common functionality and type definitions.

	Attributes:
		capabilities: Set of supported provider capabilities.
		supported_attachment_formats: Set of MIME types for supported attachments.
	"""

	capabilities: set[ProviderCapability] = set()
	supported_attachment_formats: set[str] = set()

	def __init__(self, account: Account) -> None:
		"""Initializes the engine with the given account.

		Args:
		account: The provider account configuration.
		"""
		self.account = account

	@cached_property
	@abstractmethod
	def client(self):
		"""Property to return the provider client object."""
		pass

	@cached_property
	@abstractmethod
	def models(self) -> list[ProviderAIModel]:
		"""Get models available for the provider.

		Returns:
			List of supported provider models with their configurations.
		"""
		pass

	def get_model(self, model_id: str) -> Optional[ProviderAIModel]:
		"""Retrieves a specific model by its ID.

		Args:
			model_id: Identifier of the model to retrieve.

		Returns:
			The requested model if found, None otherwise.

		Raises:
			ValueError: If multiple models are found with the same ID.
		"""
		model_list = [model for model in self.models if model.id == model_id]
		if not model_list:
			return None
		if len(model_list) > 1:
			raise ValueError(f"Multiple models with id {model_id}")
		return model_list[0]

	@abstractmethod
	def prepare_message_request(self, message: Message) -> Any:
		"""Prepare message request for provider API.

		Args:
			message: The message to prepare.

		Returns:
			The prepared message in provider-specific format.
		"""
		if not isinstance(message, Message) or message.attachments is None:
			return
		for attachment in message.attachments:
			if attachment.mime_type not in self.supported_attachment_formats:
				raise ValueError(
					f"Unsupported attachment format: {attachment.mime_type}"
				)

	@abstractmethod
	def prepare_message_response(self, response: Any) -> Message:
		"""Prepare message response.

		Args:
			response: The response to prepare.

		Returns:
			The prepared response in Message format.
		"""
		pass

	def get_messages(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None = None,
		stop_block_index: int | None = None,
	) -> list[Message]:
		"""Prepares message history for API requests.

		For group chat conversations, the history is restructured from each
		participant's point of view:
		- The current participant's own previous responses appear as ASSISTANT
		  turns (natural continuation).
		- Other participants' responses appear as USER turns, attributed with
		  ``[name]: content`` so the model sees them as external input rather
		  than its own prior output.  This prevents models from imitating the
		  ``[name]:`` prefix format in their own responses.

		Args:
			new_block: Current message block being processed.
			conversation: Full conversation history.
			system_message: Optional system-level instruction message.
			stop_block_index: Stop processing history at this index (exclusive).

		Returns:
			List of prepared messages in provider-specific format.
		"""
		from basilisk.conversation.conversation_model import (
			Message,
			MessageRoleEnum,
		)

		messages = []
		if system_message:
			messages.append(self.prepare_message_request(system_message))
		name_map: dict[str, str] = getattr(
			conversation, "_profile_name_map", {}
		)
		current_pid: str | None = getattr(
			conversation, "_current_group_participant_id", None
		)
		for i, block in enumerate(conversation.messages):
			if stop_block_index is not None and i >= stop_block_index:
				break
			if not block.response:
				continue
			if current_pid is not None and block.group_id is not None:
				# Group block: rebuild history from this participant's POV.
				pid_str = str(block.profile_id) if block.profile_id else None
				if pid_str == current_pid:
					# Own previous response: include request (if non-empty)
					# then own response as ASSISTANT.
					if block.request.content:
						messages.append(
							self.prepare_message_request(block.request)
						)
					messages.append(
						self.prepare_message_response(block.response)
					)
				else:
					# Another participant's response: frame as USER turn so
					# the model doesn't imitate the attribution format.
					other_name = (
						name_map.get(pid_str, "Other") if pid_str else "Other"
					)
					attributed = Message(
						role=MessageRoleEnum.USER,
						content=f"[{other_name}]: {block.response.content}",
					)
					messages.append(self.prepare_message_request(attributed))
			else:
				# Standard (non-group) block.
				skip_user = (
					block.group_position is not None
					and block.group_position > 0
				)
				if not skip_user:
					messages.append(self.prepare_message_request(block.request))
				messages.append(self.prepare_message_response(block.response))
		# Append the new block's request only when it carries content.
		# For group follow-ups the last USER turn is already an attribution.
		if new_block.request.content:
			messages.append(self.prepare_message_request(new_block.request))
		return messages

	@abstractmethod
	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs: dict[str, Any],
	) -> Any:
		"""Generates a completion response.

		Processes a message block and conversation to generate AI-generated content.
		Configures the generative model with optional system instructions, generation parameters, and streaming preferences.

		Args:
			new_block: Configuration block containing model ,message request and other generation settings.
			conversation: The current conversation context (paste message request and response).
			system_message: Optional system-level instruction message.
			stop_block_index: Optional index to stop processing messages at. If None, all messages are processed.
			**kwargs: Additional keyword arguments for flexible configuration.

		Returns:
			The generated content response from the provider.
		"""
		pass

	@abstractmethod
	def completion_response_with_stream(self, stream: Any, **kwargs) -> Any:
		"""Handle completion response with stream.

		Args:
			stream: Stream response from the provider.
			**kwargs: Additional keyword arguments for flexible configuration.

		Returns:
			Stream response from the provider.
		"""
		pass

	@abstractmethod
	def completion_response_without_stream(
		self, response: Any, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""Handle completion response without stream."""
		pass

	@staticmethod
	def get_user_agent() -> str:
		"""Get a user agent sting for the application."""
		return f"{APP_NAME} ({APP_SOURCE_URL})"

	def get_transcription(self, *args, **kwargs) -> str:
		"""Get transcription from audio file."""
		raise NotImplementedError(
			"Transcription not implemented for this engine"
		)
