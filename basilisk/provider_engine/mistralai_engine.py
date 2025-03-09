"""Module for MistralAI API integration.

This module provides the MistralAIEngine class for interacting with the MistralAI API,
implementing capabilities for text and image generation/processing.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING, Any, Generator

from mistralai import Mistral
from mistralai.models import ChatCompletionResponse, CompletionEvent
from mistralai.utils.eventstreaming import EventStream

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)

if TYPE_CHECKING:
	from basilisk.config import Account
from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability

log = logging.getLogger(__name__)


class MistralAIEngine(BaseEngine):
	"""Engine implementation for MistralAI API integration.

	Provides functionality for interacting with MistralAI's models, supporting text,
	image and document capabilities.

	Attributes:
		capabilities: Set of supported capabilities including text, image, STT, and TTS.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.DOCUMENT,
		ProviderCapability.OCR,
		ProviderCapability.TEXT,
	}
	supported_attachment_formats: set[str] = {
		"image/gif",
		"image/jpeg",
		"image/png",
		"image/webp",
		"application/pdf",
	}

	def __init__(self, account: Account) -> None:
		"""Initializes the MistralAI engine.

		Args:
			account: Account configuration for the MistralAI provider.
		"""
		super().__init__(account)

	@cached_property
	def client(self) -> Mistral:
		"""Creates and configures the Mistral client.

		Returns:
			Configured MistralAI client instance.
		"""
		super().client
		return Mistral(
			api_key=self.account.api_key.get_secret_value(),
			server_url=self.account.custom_base_url
			or self.account.provider.base_url,
		)

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Retrieves available MistralAI models.

		Returns:
			List of supported MistralAI models with their configurations.
		"""
		super().models
		log.debug("Getting MistralAI models")
		# See <https://docs.mistral.ai/getting-started/models/models_overview/>
		return [
			ProviderAIModel(
				id="ministral-3b-latest",
				name="Ministral 3B",
				# Translators: This is a model description
				description=_("World’s best edge model"),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="ministral-8b-latest",
				name="Ministral 8B",
				# Translators: This is a model description
				description=_(
					"Powerful edge model with extremely high performance/price ratio"
				),
				context_window=128000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="mistral-large-latest",
				name="Mistral Large",
				# Translators: This is a model description
				description=_(
					"Our top-tier reasoning model for high-complexity tasks with the latest version v2 released July 2024"
				),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="pixtral-large-latest",
				name="Pixtral Large",
				# Translators: This is a model description
				description=_(
					"Our frontier-class multimodal model released November 2024"
				),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
				vision=True,
			),
			ProviderAIModel(
				id="mistral-small-latest",
				name="Mistral Small",
				# Translators: This is a model description
				description=_(
					"Our latest enterprise-grade small model with the lastest version v2 released September 2024"
				),
				context_window=32000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="codestral-latest",
				name="Codestral",
				# Translators: This is a model description
				description=_(
					"Our cutting-edge language model for coding released May 2024"
				),
				context_window=256000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="pixtral-12b-2409",
				name="Pixtral",
				# Translators: This is a model description
				description=_(
					"A 12B model with image understanding capabilities in addition to text"
				),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
				vision=True,
			),
			ProviderAIModel(
				id="open-mistral-nemo",
				name="Mistral Nemo",
				# Translators: This is a model description
				description=_(
					"A 12B model built with the partnership with Nvidia. It is easy to use and a drop-in replacement in any system using Mistral 7B that it supersedes"
				),
				context_window=128000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="open-codestral-mamba",
				name="Codestral Mamba",
				# Translators: This is a model description
				description=_(
					"A Mamba 2 language model specialized in code generation"
				),
				context_window=256000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
		]

	def prepare_message_request(self, message: Message) -> dict[str, Any]:
		"""Prepares a message for MistralAI API request.

		Args:
			message: Message to be prepared.

		Returns:
			MistralAI API compatible message parameter.
		"""
		super().prepare_message_request(message)
		content = [{"type": "text", "text": message.content}]
		if getattr(message, "attachments", None):
			for attachment in message.attachments:
				mime_type = attachment.mime_type
				if mime_type.startswith("image/"):
					content.append(
						{"type": "image_url", "image_url": attachment.url}
					)
				else:
					content.append(
						{"type": "document_url", "document_url": attachment.url}
					)
		return {"role": message.role.value, "content": content}

	def prepare_message_response(self, response: Message) -> dict[str, Any]:
		"""Prepares an assistant message response.

		Args:
			response: Response message to be prepared.

		Returns:
			MistralAI API compatible assistant message parameter.
		"""
		super().prepare_message_response(response)
		return {
			"role": response.role.value,
			"content": [{"type": "text", "text": response.content}],
		}

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	) -> ChatCompletionResponse | EventStream[CompletionEvent]:
		"""Generates a chat completion using the MistralAI API.

		Args:
			new_block: The message block containing generation parameters.
			conversation: The conversation history context.
			system_message: Optional system message to guide the AI's behavior.
			**kwargs: Additional keyword arguments for the API request.

		Returns:
			The chat completion response.
		"""
		super().completion(new_block, conversation, system_message, **kwargs)
		params = {
			"model": new_block.model.model_id,
			"messages": self.get_messages(
				new_block, conversation, system_message
			),
			"temperature": new_block.temperature,
			"top_p": new_block.top_p,
			"stream": new_block.stream,
		}
		if new_block.max_tokens:
			params["max_tokens"] = new_block.max_tokens
		params.update(kwargs)
		if new_block.stream:
			return self.client.chat.stream(**params)
		return self.client.chat.complete(**params)

	def completion_response_with_stream(
		self, stream: Generator[CompletionEvent, None, None]
	):
		"""Processes a streaming completion response.

		Args:
			stream: Generator of chat completion chunks.

		Yields:
			Content from each chunk in the stream.
		"""
		for chunk in stream:
			delta = chunk.data.choices[0].delta
			if delta and delta.content:
				yield delta.content

	def completion_response_without_stream(
		self,
		response: ChatCompletionResponse,
		new_block: MessageBlock,
		**kwargs,
	) -> MessageBlock:
		"""Processes a non-streaming completion response.

		Args:
			response: The chat completion response.
			new_block: The message block to update with the response.
			**kwargs: Additional keyword arguments.

		Returns:
			Updated message block containing the response.
		"""
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT,
			content=response.choices[0].message.content,
		)
		return new_block
