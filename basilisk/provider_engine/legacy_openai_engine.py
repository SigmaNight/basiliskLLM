"""Module for legacy OpenAI API integration.

This module provides the OpenAIEngine class for interacting with the OpenAI completion API,
implementing capabilities for text, image, and audio generation/processing.
"""

from __future__ import annotations

import logging
from abc import ABC
from functools import cached_property
from typing import TYPE_CHECKING, Generator, Union

from openai import OpenAI
from openai.types.chat import (
	ChatCompletion,
	ChatCompletionAssistantMessageParam,
	ChatCompletionChunk,
	ChatCompletionContentPartTextParam,
	ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_content_part_image_param import (
	ChatCompletionContentPartImageParam,
	ImageURL,
)

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.provider_capability import ProviderCapability

from .base_engine import BaseEngine

if TYPE_CHECKING:
	from basilisk.config import Account

log = logging.getLogger(__name__)


class LegacyOpenAIEngine(BaseEngine, ABC):
	"""Engine implementation for OpenAI API integration.

	Provides functionality for interacting with OpenAI's models, supporting text,
	image, speech-to-text, and text-to-speech capabilities.

	Attributes:
		capabilities: Set of supported capabilities including text, image, STT, and TTS.
	"""

	def _supports_stream_usage_options(self) -> bool:
		"""Return True if the provider supports stream_options.include_usage.

		OpenAI and DeepSeek support it. OpenRouter deprecates it and may reject.
		Override in subclasses (e.g. OpenRouterEngine) to return False.
		"""
		return True

	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.TEXT,
		ProviderCapability.STT,
		ProviderCapability.TTS,
	}
	supported_attachment_formats: set[str] = {
		"image/gif",
		"image/jpeg",
		"image/png",
		"image/webp",
	}

	def __init__(self, account: Account) -> None:
		"""Initializes the OpenAI engine.

		Args:
			account: Account configuration for the OpenAI provider.
		"""
		super().__init__(account)

	@cached_property
	def client(self) -> OpenAI:
		"""Creates and configures the OpenAI client.

		Returns:
			Configured OpenAI client instance.
		"""
		organization_key = (
			self.account.active_organization_key.get_secret_value()
			if self.account.active_organization_key
			else None
		)
		return OpenAI(
			api_key=self.account.api_key.get_secret_value(),
			organization=organization_key,
			base_url=self.account.custom_base_url
			or str(self.account.provider.base_url),
		)

	def prepare_message_request(
		self, message: Message
	) -> ChatCompletionUserMessageParam:
		"""Prepares a message for OpenAI API request.

		Args:
			message: Message to be prepared.

		Returns:
			OpenAI API compatible message parameter.
		"""
		super().prepare_message_request(message)
		content = [
			ChatCompletionContentPartTextParam(
				text=message.content, type="text"
			)
		]
		if getattr(message, "attachments", None):
			for attachment in message.attachments:
				image = ImageURL(url=attachment.url, detail="auto")
				content.append(
					ChatCompletionContentPartImageParam(
						image_url=image, type="image_url"
					)
				)
		return ChatCompletionUserMessageParam(
			role=message.role.value, content=content
		)

	def prepare_message_response(
		self, response: Message
	) -> ChatCompletionAssistantMessageParam:
		"""Prepares an assistant message response.

		Args:
			response: Response message to be prepared.

		Returns:
			OpenAI API compatible assistant message parameter.
		"""
		super().prepare_message_response(response)
		return ChatCompletionAssistantMessageParam(
			role=response.role.value,
			content=[
				ChatCompletionContentPartTextParam(
					text=response.content, type="text"
				)
			],
		)

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs,
	) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
		"""Generates a chat completion using the OpenAI API.

		Args:
			new_block: The message block containing generation parameters.
			conversation: The conversation history context.
			system_message: Optional system message to guide the AI's behavior.
			stop_block_index: Optional index to stop processing messages at. If None, all messages are processed.
			**kwargs: Additional keyword arguments for the API request.

		Returns:
			Either a complete chat completion response or a generator for streaming
			chat completion chunks.
		"""
		super().completion(
			new_block, conversation, system_message, stop_block_index, **kwargs
		)
		model = self.get_model(new_block.model.model_id)
		params = {
			"model": model.id,
			"messages": self.get_messages(
				new_block,
				conversation,
				system_message,
				stop_block_index=stop_block_index,
			),
			"stream": new_block.stream,
			"temperature": new_block.temperature,
			"top_p": new_block.top_p,
		}
		if new_block.stream and self._supports_stream_usage_options():
			params["stream_options"] = {"include_usage": True}
		if new_block.max_tokens:
			params["max_tokens"] = new_block.max_tokens
		params.update(kwargs)
		params = self._filter_params_for_model(model, params)
		response = self.client.chat.completions.create(**params)
		return response

	def completion_response_with_stream(
		self,
		stream: Generator[ChatCompletionChunk, None, None],
		new_block: MessageBlock,
		**kwargs,
	):
		"""Processes a streaming completion response.

		Skips chunks with empty choices (e.g. OpenRouter SSE comments,
		processing indicators). Captures usage from final usage-only chunk
		when stream_options.include_usage is set.

		Args:
			stream: Generator of chat completion chunks.
			new_block: Block to set usage on when available.
			**kwargs: Additional arguments passed through.

		Yields:
			Content from each chunk in the stream.
		"""
		for chunk in stream:
			if not chunk.choices:
				continue
			delta = chunk.choices[0].delta
			if delta and delta.content:
				yield ("content", delta.content)

	def completion_response_without_stream(
		self, response: ChatCompletion, new_block: MessageBlock, **kwargs
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
