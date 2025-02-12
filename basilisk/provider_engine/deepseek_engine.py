"""Module for DeepSeek API integration.

This module provides the DeepSeekAIEngine class for interacting with the DeepSeek API,
implementing capabilities for text generation using various DeepSeek models.
"""

import logging
from functools import cached_property
from typing import Generator

from openai.types.chat import (
	ChatCompletion,
	ChatCompletionChunk,
	ChatCompletionUserMessageParam,
)

from basilisk.conversation import Message, MessageBlock, MessageRoleEnum

from .base_engine import ProviderAIModel
from .openai_engine import OpenAIEngine, ProviderCapability

log = logging.getLogger(__name__)


class DeepSeekAIEngine(OpenAIEngine):
	"""Engine implementation for DeepSeek API integration.

	Extends OpenAIEngine to provide DeepSeek-specific model configurations and capabilities.
	Supports text generation and reasoning capabilities.

	Attributes:
		capabilities: Set of supported capabilities (currently text only).
	"""

	capabilities: set[ProviderCapability] = {ProviderCapability.TEXT}

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Retrieves available DeepSeek models.

		Returns:
			List of supported DeepSeek models with their configurations.
		"""
		log.debug("Getting DeepSeek models")
		# See <https://api-docs.deepseek.com/quick_start/pricing>
		models = [
			ProviderAIModel(
				id="deepseek-chat",
				name="DeepSeek-V3",
				# Translators: This is a model description
				description="",
				context_window=64000,
				max_temperature=2.0,
				default_temperature=1.0,
				max_output_tokens=8000,
			),
			ProviderAIModel(
				id="deepseek-reasoner",
				name="DeepSeek-R1",
				# Translators: This is a model description
				description="",
				context_window=64000,
				max_temperature=2.0,
				default_temperature=1.0,
				max_output_tokens=8000,
			),
		]
		return models

	def completion_response_with_stream(
		self, stream: Generator[ChatCompletionChunk, None, None]
	):
		"""Processes streaming response from DeepSeek API.

		Handles both regular content and reasoning content in the stream,
		formatting reasoning content within special markdown blocks.

		Args:
			stream: Generator of chat completion chunks.

		Yields:
			Formatted text content from each chunk.
		"""
		reasoning_content_tag_sent = False
		for chunk in stream:
			delta = chunk.choices[0].delta
			if delta:
				if (
					hasattr(delta, "reasoning_content")
					and delta.reasoning_content
				):
					if not reasoning_content_tag_sent:
						reasoning_content_tag_sent = True
						yield f"```think\n{delta.reasoning_content}"
					else:
						yield delta.reasoning_content
				if delta.content:
					if reasoning_content_tag_sent:
						reasoning_content_tag_sent = False
						yield f"\n```\n\n{delta.content}"
					else:
						yield delta.content

	def completion_response_without_stream(
		self, response: ChatCompletion, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""Processes non-streaming response from DeepSeek API.

		Combines reasoning content (if present) and regular content into
		a formatted message with markdown blocks for reasoning.

		Args:
			response: The chat completion response.
			new_block: Message block to update with the response.
			**kwargs: Additional keyword arguments.

		Returns:
			Updated message block containing the formatted response.
		"""
		reasoning_content = None
		if (
			hasattr(response.choices[0].message, "reasoning_content")
			and response.choices[0].message.reasoning_content
		):
			reasoning_content = response.choices[0].message.reasoning_content
		content = response.choices[0].message.content
		if reasoning_content:
			content = f"```think\n{reasoning_content}\n```\n\n{content}"
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT, content=content
		)
		return new_block

	def prepare_message_response(
		self, message: Message
	) -> ChatCompletionUserMessageParam:
		"""Prepares a message response for the DeepSeek API.

		Args:
			message: Message to be prepared.

		Returns:
			DeepSeek API compatible message parameter.
		"""
		return ChatCompletionUserMessageParam(
			role=message.role.value, content=message.content
		)
