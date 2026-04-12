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
from basilisk.provider_engine.dynamic_model_loader import (
	get_last_load_error,
	load_models_from_url,
)

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
	MODELS_JSON_URL: str | None = None

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

	def _postprocess_models(
		self, models: list[ProviderAIModel]
	) -> list[ProviderAIModel]:
		"""Hook to adjust dynamically loaded models for provider-specific parity."""
		return models

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Get models available for the provider.

		Returns:
			List of supported provider models with their configurations.
		"""
		if not self.MODELS_JSON_URL:
			raise NotImplementedError(
				f"{self.__class__.__name__} must override models or set MODELS_JSON_URL"
			)
		return self._postprocess_models(
			load_models_from_url(self.MODELS_JSON_URL)
		)

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

	def get_model_loading_error(self) -> str | None:
		"""Return the latest model-loading error for this engine."""
		if not self.MODELS_JSON_URL:
			return None
		return get_last_load_error(self.MODELS_JSON_URL)

	def invalidate_models_cache(self) -> None:
		"""Clear the cached model list so the next access reloads it."""
		self.__dict__.pop("models", None)

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

		Args:
			new_block: Current message block being processed.
			conversation: Full conversation history.
			system_message: Optional system-level instruction message.
			stop_block_index: Optional index to stop processing messages at. If None, all messages are processed.

		Returns:
			List of prepared messages in provider-specific format.
		"""
		messages = []
		if system_message:
			messages.append(self.prepare_message_request(system_message))
		for i, block in enumerate(conversation.messages):
			if stop_block_index is not None and i >= stop_block_index:
				break
			if not block.response:
				continue
			messages.extend(
				[
					self.prepare_message_request(block.request),
					self.prepare_message_response(block.response),
				]
			)
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
		"""Handle completion response without stream.

		TODO: unify reasoning/thinking handling across providers so reasoning
		traces are modeled as provider-agnostic metadata (not mixed into plain
		response content), with a UI toggle to show/hide reasoning output.
		"""
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
