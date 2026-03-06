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
from basilisk.provider_engine.provider_ui_spec import (
	AudioOutputUISpec,
	ReasoningUISpec,
)

if TYPE_CHECKING:
	from basilisk.config import Account


def _load_models_from_json_url(url: str) -> list[ProviderAIModel]:
	"""Load models from model-metadata JSON URL. Deferred import to avoid circular deps."""
	from basilisk.provider_engine.dynamic_model_loader import (
		load_models_from_url,
	)

	return load_models_from_url(url)


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

	# Override in subclasses that load from model-metadata JSON; None for custom loaders (OpenRouter, Ollama, etc.)
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
		"""Optional hook to mutate models after loading from JSON. Override in subclasses."""
		return models

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Get models available for the provider.

		When MODELS_JSON_URL is set, loads from that URL and applies _postprocess_models.
		Otherwise the subclass must override this property (e.g. OpenRouter, Ollama).
		"""
		url = self.MODELS_JSON_URL
		if url:
			return self._postprocess_models(_load_models_from_json_url(url))
		raise NotImplementedError(
			"Subclass must implement models() or set MODELS_JSON_URL"
		)

	def model_supports_web_search(self, model: ProviderAIModel) -> bool:
		"""Return True if this model supports web search.

		Override in engines for provider-specific exclusions (e.g. OpenAI
		gpt-4.1-nano, gpt-5 with minimal reasoning).

		Args:
			model: The model to check.

		Returns:
			True if web search can be used with this model.
		"""
		if ProviderCapability.WEB_SEARCH not in self.capabilities:
			return False
		if model.web_search_capable:
			return True
		return model.supports_parameter("tools")

	# Param keys that may be filtered by model.supported_parameters
	_FILTERABLE_PARAMS = frozenset(
		{
			"temperature",
			"top_p",
			"max_tokens",
			"frequency_penalty",
			"presence_penalty",
			"seed",
			"top_k",
		}
	)

	def _filter_params_for_model(
		self, model: ProviderAIModel, params: dict[str, Any]
	) -> dict[str, Any]:
		"""Filter generation params to only those the model supports.

		Structural params (model, input, messages, stream, tools, etc.) are
		always included. When supported_parameters is empty (legacy), returns
		params unchanged.

		Args:
			model: The model to filter for.
			params: Raw params dict.

		Returns:
			Filtered params dict.
		"""
		supported = model.supported_parameters
		if not supported:
			return params
		result = {}
		for k, v in params.items():
			if k in self._FILTERABLE_PARAMS and k not in supported:
				continue
			result[k] = v
		return result

	def get_web_search_tool_definitions(
		self, model: ProviderAIModel
	) -> list[Any]:
		"""Return tool definitions for web search. Override in each engine.

		Args:
			model: The model (for provider-specific tool variants).

		Returns:
			List of tool dicts or objects to add to the API request.
		"""
		return []

	def get_reasoning_ui_spec(self, model: ProviderAIModel) -> ReasoningUISpec:
		"""Return UI spec for reasoning mode controls. Override per provider.

		Engine injects its own settings—no provider_id checks in presenter.

		Args:
			model: The selected model.

		Returns:
			ReasoningUISpec describing what controls to show.
		"""
		if not model.reasoning_capable or model.reasoning:
			return ReasoningUISpec(show=False)
		return ReasoningUISpec(show=True)

	def get_audio_output_spec(
		self, model: ProviderAIModel
	) -> AudioOutputUISpec | None:
		"""Return UI spec for audio output (TTS) controls. Override per provider.

		Returns None when model does not support audio output.

		Args:
			model: The selected model.

		Returns:
			AudioOutputUISpec with voices, or None.
		"""
		return None

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
