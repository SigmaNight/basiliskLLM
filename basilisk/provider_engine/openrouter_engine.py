"""Module for OpenRouter API integration.

This module provides the OpenRouterEngine class for interacting with the OpenRouter API,
implementing capabilities for text and image generation across multiple AI models.
"""

import logging
from typing import Generator, Union

import httpx
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from basilisk.conversation import Conversation, Message, MessageBlock
from basilisk.decorators import measure_time
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

from .dynamic_model_loader import parse_model_rows
from .legacy_openai_engine import LegacyOpenAIEngine

log = logging.getLogger(__name__)


class OpenRouterEngine(LegacyOpenAIEngine):
	"""Engine implementation for OpenRouter API integration.

	Extends OpenAIEngine to provide OpenRouter-specific model configurations and capabilities.
	Supports accessing multiple AI models through a single API.

	Attributes:
		capabilities: Set of supported capabilities including text and image generation.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
		ProviderCapability.WEB_SEARCH,
	}

	@measure_time
	def _load_models(self) -> list[ProviderAIModel]:
		"""Retrieves available models from OpenRouter API.

		Returns:
			List of supported models with their configurations.
		"""
		log.debug("Getting openRouter models")
		url = "https://openrouter.ai/api/v1/models"
		response = httpx.get(url, headers={"User-Agent": self.get_user_agent()})
		if response.status_code == 200:
			data = response.json()
			models = parse_model_rows(data.get("data", []))
			log.debug("Got %d models", len(models))
			return models
		else:
			log.error(
				"Failed to get models from '%s'. Response: %s",
				url,
				response.text,
			)
		return []

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
		"""Generates a chat completion using the OpenAI API.

		Args:
			new_block: The message block containing generation parameters.
			conversation: The conversation history context.
			system_message: Optional system message to guide the AI's behavior.
			**kwargs: Additional keyword arguments for the API request.

		Returns:
			Either a complete chat completion response or a generator for streaming
			chat completion chunks.
		"""
		extra_body = kwargs.get("extra_body", {})
		plugins = []
		if "web_search_mode" in kwargs:
			if kwargs["web_search_mode"]:
				plugins.append(
					{
						"id": "web",
						"max_results": 5,
						"search_prompt": "Consider these web results when forming your response:",
					}
				)
			kwargs.pop("web_search_mode")

		if plugins:
			extra_body["plugins"] = plugins
		return super().completion(
			new_block,
			conversation,
			system_message,
			extra_body=extra_body,
			**kwargs,
		)
