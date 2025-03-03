"""Module for Google Gemini API integration.

This module provides the GeminiEngine class for interacting with the Google Gemini API,
implementing capabilities for text and image handling using Google's generative AI models.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING

import google.generativeai as genai

from basilisk.conversation import (
	AttachmentFileTypes,
	Conversation,
	ImageFile,
	Message,
	MessageBlock,
	MessageRoleEnum,
)

from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability

if TYPE_CHECKING:
	from basilisk.config import Account

logger = logging.getLogger(__name__)


class GeminiEngine(BaseEngine):
	"""Engine implementation for Google Gemini API integration.

	Provides specific functionality for interacting with Google's Gemini models,
	supporting both text and image capabilities.

	Attributes:
		capabilities: Set of supported capabilities including text and image processing.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
	}
	supported_attachment_formats: set[str] = {
		"image/png",
		"image/jpeg",
		"image/webp",
		"image/heic",
		"image/heif",
	}

	def __init__(self, account: Account) -> None:
		"""Initializes the engine with the given account.

		Args:
			account: The provider account configuration.
		"""
		super().__init__(account)
		genai.configure(api_key=self.account.api_key.get_secret_value())

	@property
	def client(self) -> None:
		"""Property to return the client object for the provider.

		Raises:
			NotImplementedError: Getting client is not supported for Gemini.
		"""
		raise NotImplementedError("Getting client not supported for Gemini")

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Get models available for the provider.

		Returns:
			List of supported provider models with their configurations.
		"""
		# See <https://ai.google.dev/gemini-api/docs/models/gemini?hl=en>
		models = []
		for model in genai.list_models():
			if "generateContent" in model.supported_generation_methods:
				models.append(
					ProviderAIModel(
						id=model.name,
						name=model.display_name,
						description=model.description,
						context_window=(
							model.output_token_limit + model.input_token_limit
						),
						max_output_tokens=model.output_token_limit,
						vision=True,
						reasoning="thinking" in model.name,
						default_temperature=model.temperature,
					)
				)
		return models

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

	def convert_image(self, image: ImageFile) -> genai.protos.Part:
		"""Converts internal image representation to Gemini API format.

		Args:
			image: Internal image file object.

		Returns:
			Gemini API compatible image part.

		Raises:
			NotImplementedError: If image URL is used (not supported).
		"""
		if image.type == AttachmentFileTypes.URL:
			raise NotImplementedError("Image URL not supported")
		with image.send_location.open("rb") as f:
			blob = genai.protos.Blob(mime_type=image.mime_type, data=f.read())
		return genai.protos.Part(inline_data=blob)

	def convert_message_content(self, message: Message) -> genai.protos.Content:
		"""Converts internal message to Gemini API content format.

		Args:
			message: Internal message object.

		Returns:
			Gemini API compatible content object.
		"""
		role = self.convert_role(message.role)
		parts = [genai.protos.Part(text=message.content)]
		if message.attachments:
			for attachment in message.attachments:
				parts.append(self.convert_image(attachment))
		return genai.protos.Content(role=role, parts=parts)

	# Implement abstract methods from BaseEngine with the same method for request and response
	prepare_message_request = convert_message_content
	prepare_message_response = convert_message_content

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	) -> genai.types.GenerateContentResponse:
		"""Generates a completion response using the Gemini AI model with specified configuration.

		Processes a message block and conversation to generate AI-generated content through the Gemini API. Configures the generative model with optional system instructions, generation parameters, and streaming preferences.

		Args:
			new_block: Configuration block containing message request, model and other generation settings
			conversation: The current conversation context (past message request and response)
			system_message: Optional system-level instruction message
			**kwargs: Additional keyword arguments for flexible configuration

		Returns:
			The generated content response from the Gemini model
		"""
		super().completion(new_block, conversation, system_message, **kwargs)
		model = genai.GenerativeModel(
			model_name=new_block.model.model_id,
			system_instruction=system_message.content
			if system_message
			else None,
		)

		generation_config = genai.GenerationConfig(
			max_output_tokens=new_block.max_tokens
			if new_block.max_tokens
			else None,
			temperature=new_block.temperature,
			top_p=new_block.top_p,
		)
		return model.generate_content(
			contents=self.get_messages(new_block, conversation, None),
			generation_config=generation_config,
			stream=new_block.stream,
		)

	def completion_response_without_stream(
		self,
		response: genai.types.GenerateContentResponse,
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
		self, stream: genai.types.GenerateContentResponse, **kwargs
	) -> genai.types.GenerateContentResponse:
		"""Handle completion response with stream.

		Args:
			stream: Stream response from the provider
			**kwargs: Additional keyword arguments for flexible configuration

		Returns:
			Stream response from the provider
		"""
		for chunk in stream:
			chunk_text = chunk.text
			if chunk_text:
				yield chunk_text
