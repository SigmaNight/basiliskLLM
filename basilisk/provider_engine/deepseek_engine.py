"""Module for DeepSeek API integration.

This module provides the DeepSeekAIEngine class for interacting with the DeepSeek API,
implementing capabilities for text generation using various DeepSeek models.
"""

import logging
from typing import Generator

from openai.types.chat import (
	ChatCompletion,
	ChatCompletionAssistantMessageParam,
	ChatCompletionChunk,
)

from basilisk.conversation import Message, MessageBlock, MessageRoleEnum
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

from .legacy_openai_engine import LegacyOpenAIEngine

log = logging.getLogger(__name__)

# Reasoning-only models (always-on thinking; no toggle)
_DEEPSEEK_REASONING_ONLY_IDS = frozenset(
	{
		"deepseek-reasoner-latest",
		"deepseek-v3.2-speciale",
		"deepseek-r1",
		"deepseek-r1-0528",
	}
)


class DeepSeekAIEngine(LegacyOpenAIEngine):
	"""Engine implementation for DeepSeek API integration.

	Extends LegacyOpenAIEngine to provide DeepSeek-specific model configurations and capabilities.
	Supports text generation and reasoning capabilities.

	Attributes:
		capabilities: Set of supported capabilities (currently text only).
	"""

	capabilities: set[ProviderCapability] = {ProviderCapability.TEXT}

	MODELS_JSON_URL = "https://raw.githubusercontent.com/SigmaNight/model-metadata/master/data/deepseek.json"

	def _postprocess_models(
		self, models: list[ProviderAIModel]
	) -> list[ProviderAIModel]:
		for m in models:
			if m.id in _DEEPSEEK_REASONING_ONLY_IDS:
				m.reasoning = True
				m.reasoning_capable = False
		return models

	def completion_response_with_stream(
		self,
		stream: Generator[ChatCompletionChunk, None, None],
		new_block: MessageBlock | None = None,
		**kwargs,
	):
		"""Processes streaming response from DeepSeek API.

		Yields ("content", chunk) with reasoning mixed into content using
		```think``` markers. Separate reasoning storage is in feat/reasoning-storage.
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
						yield (
							"content",
							f"```think\n{delta.reasoning_content}",
						)
					else:
						yield ("content", delta.reasoning_content)
				if delta.content:
					if reasoning_content_tag_sent:
						reasoning_content_tag_sent = False
						yield ("content", f"\n```\n\n{delta.content}")
					else:
						yield ("content", delta.content)

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
	) -> ChatCompletionAssistantMessageParam:
		"""Prepares a message response for the DeepSeek API.

		Args:
			message: Message to be prepared.

		Returns:
			DeepSeek API compatible message parameter.
		"""
		return ChatCompletionAssistantMessageParam(
			role=message.role.value, content=message.content
		)
