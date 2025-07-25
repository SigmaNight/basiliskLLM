"""Module for Google Gemini API integration.

This module provides the GeminiEngine class for interacting with the Google Gemini API,
implementing capabilities for text and image handling using Google's generative AI models.
"""

from __future__ import annotations

import logging
import re
from functools import cached_property
from typing import Iterator

from google import genai
from google.genai.types import (
	Content,
	GenerateContentConfig,
	GenerateContentResponse,
	GoogleSearch,
	Part,
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
from basilisk.decorators import measure_time

from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability

logger = logging.getLogger(__name__)

re_gemini_model = re.compile(r"Gemini (\d+\.\d+)")


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

	@cached_property
	def client(self) -> genai.Client:
		"""Property to return the client object for the provider.

		Returns:
			Client object for the provider, initialized with the API key.
		"""
		return genai.Client(api_key=self.account.api_key.get_secret_value())

	@cached_property
	@measure_time
	def models(self) -> list[ProviderAIModel]:
		"""Get models available for the provider.

		Returns:
			List of supported provider models with their configurations.
		"""
		models = []
		for model in self.client.models.list():
			if "generateContent" not in model.supported_actions:
				continue
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
				)
			)
		gemini_xy_models = [
			m for m in models if re_gemini_model.match(m.display_name)
		]
		gemini_xy_models.sort(
			key=lambda x: -float(re_gemini_model.match(x.display_name).group(1))
		)
		other_models = [
			m for m in models if not re_gemini_model.match(m.display_name)
		]
		return gemini_xy_models + other_models

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
		web_search = kwargs.pop("web_search_mode", False)
		tools = None
		if web_search:
			tools = [Tool(google_search=GoogleSearch())]
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
		self, stream: Iterator[GenerateContentResponse], **kwargs
	) -> Iterator[str]:
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
