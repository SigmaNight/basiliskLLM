"""Module for OpenRouter API integration.

This module provides the OpenRouterEngine class for interacting with the OpenRouter API,
implementing capabilities for text and image generation across multiple AI models.
"""

import logging
from datetime import datetime
from decimal import Decimal, getcontext
from functools import cached_property
from typing import Generator, Union

import httpx
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from basilisk.conversation import Conversation, Message, MessageBlock
from basilisk.decorators import measure_time
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

from .legacy_openai_engine import LegacyOpenAIEngine

log = logging.getLogger(__name__)

getcontext().prec = 20


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

	def summarize_pricing(self, pricing: dict[str, dict[str, str]]) -> str:
		"""Formats pricing information into a human-readable string.

		Args:
			pricing: Raw pricing data from the API.

		Returns:
			Formatted pricing information string.
		"""
		if not isinstance(pricing, dict):
			return ""
		out = "\n"
		for usage_type, price in pricing.items():
			if price is None or price == '0':
				continue
			if usage_type == "image":
				price_1k = round(Decimal(price) * Decimal(1000), 3)
				if price_1k == 0:
					continue
				out += f"  {usage_type}: ${price_1k}/K input imgs (${price}/input img)\n"
			else:
				price_1m = round(Decimal(price) * Decimal(1000000), 2)
				out += (
					f"  {usage_type}: ${price_1m}/M tokens (${price}/token)\n"
				)
		return out.rstrip()

	@cached_property
	@measure_time
	def models(self) -> list[ProviderAIModel]:
		"""Retrieves available models from OpenRouter API.

		Returns:
			List of supported models with their configurations.
		"""
		models = []
		log.debug("Getting openRouter models")
		url = "https://openrouter.ai/api/v1/models"
		response = httpx.get(url, headers={"User-Agent": self.get_user_agent()})
		if response.status_code == 200:
			data = response.json()
			for model in sorted(data["data"], key=lambda m: m["name"].lower()):
				extra_info = {}
				for k, v in sorted(model.items()):
					match k:
						case (
							"id"
							| "name"
							| "description"
							| "context_length"
							| "top_provider"
						):
							continue
						case "pricing":
							summary = self.summarize_pricing(v)
							if summary:
								extra_info["Pricing"] = summary
						case "created":
							extra_info[k] = datetime.fromtimestamp(v).strftime(
								"%Y-%m-%d %H:%M:%S"
							)
						case _:
							if v is None:
								continue
							extra_info[k.replace('_', ' ')] = v
				models.append(
					ProviderAIModel(
						id=model["id"],
						name=model["name"],
						description=model["description"],
						context_window=int(model["context_length"]),
						max_output_tokens=model.get("top_provider").get(
							"max_completion_tokens"
						)
						or -1,
						max_temperature=2.0,
						vision="text+image->text"
						in model.get("architecture", {}).get("modality", ''),
						extra_info=extra_info,
					)
				)
			log.debug("Got %d models", len(models))
		else:
			log.error(
				"Failed to get models from '%s'. Response: %s",
				url,
				response.text,
			)
		return models

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
