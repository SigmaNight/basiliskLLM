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

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.decorators import measure_time
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

from .legacy_openai_engine import LegacyOpenAIEngine
from .provider_ui_spec import ReasoningUISpec

log = logging.getLogger(__name__)

getcontext().prec = 20

# OpenRouter model IDs use provider/model format. Per OpenRouter docs:
# - Effort (OpenAI-style): openai, x-ai (Grok)
# - Max tokens (Anthropic-style): anthropic, google (Gemini thinking), alibaba (Qwen)
_OPENROUTER_EFFORT_PROVIDERS = frozenset({"openai", "x-ai"})
_OPENROUTER_BUDGET_PROVIDERS = frozenset({"anthropic", "google", "alibaba"})


def _openrouter_reasoning_provider(model_id: str) -> str | None:
	"""Extract provider prefix from OpenRouter model ID (e.g. anthropic/claude-*)."""
	if not model_id or "/" not in model_id:
		return None
	return model_id.split("/", 1)[0].lower()


class OpenRouterEngine(LegacyOpenAIEngine):
	"""Engine implementation for OpenRouter API integration.

	Extends OpenAIEngine to provide OpenRouter-specific model configurations and capabilities.
	Supports accessing multiple AI models through a single API.

	Attributes:
		capabilities: Set of supported capabilities including text and image generation.
	"""

	def _supports_stream_usage_options(self) -> bool:
		"""OpenRouter deprecates stream_options.include_usage and may reject it."""
		return False

	def get_reasoning_ui_spec(self, model: ProviderAIModel) -> ReasoningUISpec:
		"""OpenRouter: effort or budget per provider. No adaptive (API uses max_tokens only)."""
		spec = super().get_reasoning_ui_spec(model)
		if not spec.show:
			return spec
		provider = _openrouter_reasoning_provider(model.id or "")
		if provider in _OPENROUTER_BUDGET_PROVIDERS:
			# Anthropic, Gemini, Alibaba: max_tokens only. OpenRouter does not support
			# adaptive thinking (thinking.type: "adaptive") for Claude 4.x.
			return ReasoningUISpec(
				show=True,
				show_adaptive=False,
				show_budget=True,
				show_effort=False,
				budget_default=16000,
				budget_max=128000,
			)
		# Per OpenRouter docs: effort none/minimal/low/medium/high/xhigh
		effort_opts = ("minimal", "low", "medium", "high", "xhigh")
		if provider in _OPENROUTER_EFFORT_PROVIDERS:
			return ReasoningUISpec(
				show=True,
				show_adaptive=False,
				show_budget=False,
				show_effort=True,
				effort_options=effort_opts,
				effort_label="Reasoning effort:",
			)
		# Default: effort (DeepSeek, etc.)
		return ReasoningUISpec(
			show=True,
			show_adaptive=False,
			show_budget=False,
			show_effort=True,
			effort_options=effort_opts,
			effort_label="Reasoning effort:",
		)

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
			if price is None or price == "0":
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
							extra_info[k.replace("_", " ")] = v
				arch = model.get("architecture") or {}
				modality = arch.get("modality", "")
				output_mods = arch.get("output_modalities") or []
				if isinstance(output_mods, str):
					output_mods = [output_mods]
				image_output = "image" in output_mods
				audio_output = "audio" in output_mods
				supported = model.get("supported_parameters") or []
				if isinstance(supported, list):
					supported = [str(s).lower() for s in supported]
				else:
					supported = []
				reasoning_capable = (
					"reasoning" in supported or "include_reasoning" in supported
				)
				models.append(
					ProviderAIModel(
						id=model["id"],
						name=model["name"],
						description=model["description"],
						context_window=int(model["context_length"]),
						max_output_tokens=(model.get("top_provider") or {}).get(
							"max_completion_tokens"
						)
						or -1,
						max_temperature=2.0,
						vision="image" in modality,
						audio="audio" in modality,
						document="file" in modality,
						image_output=image_output,
						audio_output=audio_output,
						reasoning_capable=reasoning_capable,
						supported_parameters=supported,
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
		stop_block_index: int | None = None,
		**kwargs,
	) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
		"""Generates a chat completion using the OpenRouter API."""
		extra_body = dict(kwargs.get("extra_body") or {})
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
		model = self.get_model(new_block.model.model_id)
		if model.reasoning_capable and new_block.reasoning_mode:
			provider = _openrouter_reasoning_provider(model.id or "")
			if provider in _OPENROUTER_BUDGET_PROVIDERS:
				extra_body["reasoning"] = {
					"max_tokens": new_block.reasoning_budget_tokens or 16000
				}
			else:
				effort = (new_block.reasoning_effort or "medium").lower()
				if effort not in ("minimal", "low", "medium", "high", "xhigh"):
					effort = "medium"
				extra_body["reasoning"] = {"effort": effort}
		kwargs["extra_body"] = extra_body
		return super().completion(
			new_block,
			conversation,
			system_message,
			stop_block_index=stop_block_index,
			**kwargs,
		)

	def completion_response_with_stream(
		self,
		stream: Generator[ChatCompletionChunk, None, None],
		new_block: MessageBlock,
		**kwargs,
	):
		"""Process streaming response; yield reasoning and content chunks."""
		for chunk in stream:
			if not chunk.choices:
				continue
			delta = chunk.choices[0].delta
			if not delta:
				continue
			reasoning = getattr(delta, "reasoning", None)
			if reasoning:
				yield ("reasoning", reasoning)
			if delta.content:
				yield ("content", delta.content)

	def completion_response_without_stream(
		self, response: ChatCompletion, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""Process non-streaming response; extract reasoning and content."""
		msg = response.choices[0].message
		content = msg.content or ""
		reasoning = getattr(msg, "reasoning", None)
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT, content=content, reasoning=reasoning
		)
		return new_block
