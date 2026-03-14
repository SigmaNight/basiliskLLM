"""Module for Google Gemini API integration.

This module provides the GeminiEngine class for interacting with the Google Gemini API,
implementing capabilities for text and image handling using Google's generative AI models.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import Iterator

from google import genai
from google.genai.types import (
	Content,
	GenerateContentConfig,
	GenerateContentResponse,
	GoogleSearch,
	Part,
	ThinkingConfig,
	ThinkingLevel,
	Tool,
)

from basilisk.conversation import (
	AttachmentFile,
	AttachmentFileTypes,
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)

from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability
from .provider_ui_spec import ReasoningUISpec

logger = logging.getLogger(__name__)


class GeminiEngine(BaseEngine):
	"""Engine implementation for Google Gemini API integration.

	Provides specific functionality for interacting with Google's Gemini models,
	supporting both text and image capabilities.

	Attributes:
		capabilities: Set of supported capabilities including text and image processing.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.AUDIO,
		ProviderCapability.DOCUMENT,
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
		ProviderCapability.WEB_SEARCH,
		ProviderCapability.VIDEO,
	}

	supported_attachment_formats: set[str] = {
		"application/pdf",
		"application/javascript",
		"audio/wav",
		"audio/mpeg",
		"audio/aac",
		"audio/ogg",
		"audio/x-aiff",
		"audio/x-flac",
		"image/png",
		"image/jpeg",
		"image/webp",
		"image/heic",
		"image/heif",
		"text/css",
		"text/csv",
		"text/html",
		"text/plain",
		"text/xml",
		"text/x-python",
		"video/avi",
		"video/mp4",
		"video/mpeg",
		"video/quicktime",
		"video/webm",
		"video/3gpp",
	}

	MODELS_JSON_URL = "https://raw.githubusercontent.com/SigmaNight/model-metadata/master/data/google.json"

	@cached_property
	def client(self) -> genai.Client:
		"""Property to return the client object for the provider.

		Returns:
			Client object for the provider, initialized with the API key.
		"""
		return genai.Client(api_key=self.account.api_key.get_secret_value())

	def model_supports_web_search(self, model: ProviderAIModel) -> bool:
		"""Gemini supports Google Search via tools for models with tools capability."""
		return super().model_supports_web_search(model)

	def get_web_search_tool_definitions(
		self, model: ProviderAIModel
	) -> list[Tool]:
		"""Return Google Search tool for grounding."""
		return [Tool(google_search=GoogleSearch())]

	def get_reasoning_ui_spec(self, model: ProviderAIModel) -> ReasoningUISpec:
		"""Gemini: gemini-2 uses budget; gemini-3 uses effort (low/medium/high)."""
		spec = super().get_reasoning_ui_spec(model)
		if not spec.show:
			return spec
		model_id = (model.id or "").lower()
		if "gemini-3" in model_id:
			return ReasoningUISpec(
				show=True,
				show_adaptive=False,
				show_budget=False,
				show_effort=True,
				effort_options=("low", "medium", "high"),
				effort_label="Thinking level:",
			)
		# Gemini 2.5: thinking_budget
		return ReasoningUISpec(
			show=True,
			show_adaptive=False,
			show_budget=True,
			show_effort=False,
			budget_default=16000,
			budget_max=128000,
		)

	def convert_role(self, role: MessageRoleEnum) -> str:
		"""Converts internal role enum to Gemini API role string.

		Args:
			role: Internal message role enum value.

		Returns:
			String representation of the role for Gemini API.

		Raises:
			NotImplementedError: If system role is used (not supported by Gemini).
		"""
		if role == MessageRoleEnum.ASSISTANT:
			return "model"
		elif role == MessageRoleEnum.USER:
			return "user"
		elif role == MessageRoleEnum.SYSTEM:
			raise NotImplementedError(
				"System role must be set on the model instance"
			)

	def convert_attachment(self, attachment: AttachmentFile) -> Part:
		"""Converts internal attachment representation to Gemini 'part'.

		Args:
			attachment: Internal attachment object.

		Returns:
			Gemini API compatible content part.

		Raises:
			ValueError: If the attachment type is not supported.
		"""
		if not attachment.mime_type:
			raise ValueError("Attachment mime type is not set")
		if attachment.type == AttachmentFileTypes.URL:
			return Part.from_uri(
				file_uri=attachment.url, mime_type=attachment.mime_type
			)
		with attachment.send_location.open("rb") as f:
			return Part.from_bytes(
				mime_type=attachment.mime_type, data=f.read()
			)

	def convert_message_content(self, message: Message) -> Content:
		"""Converts internal message to Gemini API content format.

		Args:
			message: Internal message object.

		Returns:
			Gemini API compatible content object.
		"""
		role = self.convert_role(message.role)
		parts = [Part(text=message.content)]
		if message.attachments:
			for attachment in message.attachments:
				parts.append(self.convert_attachment(attachment))
		return Content(role=role, parts=parts)

	# Implement abstract methods from BaseEngine with the same method for request and response
	prepare_message_request = convert_message_content
	prepare_message_response = convert_message_content

	def _build_thinking_config(
		self, model: ProviderAIModel | None, new_block: MessageBlock
	) -> ThinkingConfig | None:
		"""Build ThinkingConfig for Gemini 2.5 (thinking_budget) or 3 (thinking_level).

		Gemini 2.5 uses thinking_budget (tokens, -1=auto); Gemini 3 uses thinking_level.
		Only add config when reasoning_mode is on and model supports it.
		"""
		if (
			not model
			or not model.reasoning_capable
			or not new_block.reasoning_mode
		):
			return None
		model_id = (model.id or "").lower()
		if "gemini-3" in model_id:
			effort = (new_block.reasoning_effort or "high").lower()
			level_map = {
				"low": ThinkingLevel.LOW,
				"medium": ThinkingLevel.MEDIUM,
				"high": ThinkingLevel.HIGH,
			}
			thinking_level = level_map.get(effort, ThinkingLevel.HIGH)
			return ThinkingConfig(thinking_level=thinking_level)
		# Gemini 2.5: thinking_budget (tokens). -1 = auto/dynamic per API.
		budget = new_block.reasoning_budget_tokens
		if budget is None:
			budget = -1
		return ThinkingConfig(thinking_budget=budget)

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs,
	) -> GenerateContentResponse | Iterator[GenerateContentResponse]:
		"""Generates a completion response using the Gemini AI model with specified configuration.

		Processes a message block and conversation to generate AI-generated content through the Gemini API. Configures the generative model with optional system instructions, generation parameters, and streaming preferences.

		Args:
			new_block: Configuration block containing message request, model and other generation settings
			conversation: The current conversation context (past message request and response)
			system_message: Optional system-level instruction message
			stop_block_index: Optional index to stop processing messages at. If None, all messages are processed
			**kwargs: Additional keyword arguments for flexible configuration

		Returns:
			The generated content response from the Gemini model
		"""
		super().completion(
			new_block, conversation, system_message, stop_block_index, **kwargs
		)
		model = self.get_model(new_block.model.model_id)
		tools = None
		web_search = kwargs.pop("web_search_mode", False)
		if web_search and model and self.model_supports_web_search(model):
			tools = self.get_web_search_tool_definitions(model)

		thinking_config = self._build_thinking_config(model, new_block)

		config = GenerateContentConfig(
			system_instruction=system_message.content
			if system_message
			else None,
			max_output_tokens=new_block.max_tokens
			if new_block.max_tokens
			else None,
			temperature=new_block.temperature,
			top_p=new_block.top_p,
			tools=tools,
			thinking_config=thinking_config,
		)

		generate_kwargs = {
			"model": new_block.model.model_id,
			"config": config,
			"contents": self.get_messages(
				new_block, conversation, stop_block_index=stop_block_index
			),
		}
		if new_block.stream:
			return self.client.models.generate_content_stream(**generate_kwargs)
		else:
			return self.client.models.generate_content(**generate_kwargs)

	def completion_response_without_stream(
		self,
		response: GenerateContentResponse,
		new_block: MessageBlock,
		**kwargs,
	) -> MessageBlock:
		"""Handle completion response without stream.

		Args:
			response: Response from the provider
			new_block: Configuration block containing message request and model
			**kwargs: Additional keyword arguments for flexible configuration

		Returns:
			Message block containing the response content
		"""
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT, content=response.text
		)
		return new_block

	def completion_response_with_stream(
		self,
		stream: Iterator[GenerateContentResponse],
		new_block: MessageBlock,
		**kwargs,
	) -> Iterator[str]:
		"""Handle completion response with stream.

		Args:
			stream: Stream response from the provider
			new_block: Block to set usage on when available
			**kwargs: Additional arguments passed through.

		Returns:
			Stream response from the provider
		"""
		for chunk in stream:
			chunk_text = chunk.text
			if chunk_text:
				yield chunk_text
