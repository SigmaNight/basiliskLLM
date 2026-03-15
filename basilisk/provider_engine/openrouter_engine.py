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

from .dynamic_model_loader import (
	_get_context_length,
	_get_created,
	_get_default_params,
	_get_max_completion_tokens,
	_has_reasoning_capable,
	_has_web_search_capable,
	_modality_flags,
)
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
							| "default_parameters"
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
				context_window = _get_context_length(model)
				max_output_tokens = _get_max_completion_tokens(model)
				modalities = _modality_flags(model.get("architecture") or {})
				supported = model.get("supported_parameters") or []
				if isinstance(supported, list):
					supported = [str(s).lower() for s in supported]
				else:
					supported = []
				reasoning_capable = _has_reasoning_capable(supported)
				web_search_capable = _has_web_search_capable(model, supported)
				default_params = _get_default_params(model)
				extra_info["default_parameters"] = default_params
				def_temp = default_params.get("temperature")
				default_temperature = (
					float(def_temp) if def_temp is not None else 1.0
				)
				created = _get_created(model)
				models.append(
					ProviderAIModel(
						id=model["id"],
						name=model["name"],
						description=model["description"],
						context_window=context_window,
						max_output_tokens=max_output_tokens,
						max_temperature=2.0,
						default_temperature=default_temperature,
						vision=modalities["vision"],
						audio=modalities["audio"],
						document=modalities["document"],
						image_output=modalities["image_output"],
						audio_output=modalities["audio_output"],
						reasoning_capable=reasoning_capable,
						web_search_capable=web_search_capable,
						created=created,
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
