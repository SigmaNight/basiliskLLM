"""Module for xAI API integration.

This module provides the XAIEngine class for interacting with the xAI API
via the Responses API, with support for text, image, and web search.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from openai import OpenAI

from basilisk.conversation import Conversation, MessageBlock
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

from .responses_api_engine import ResponsesAPIEngine

log = logging.getLogger(__name__)

# Reasoning-only models (always-on; no reasoning_effort toggle)
_XAI_REASONING_ONLY_IDS = frozenset(
	{
		"grok-4-1-fast-reasoning",
		"grok-4-fast-reasoning",
		"grok-4-0709",
		"grok-code-fast-1",
	}
)

# Models that support reasoning_effort param (low/high)
_XAI_REASONING_EFFORT_IDS = frozenset({"grok-3-mini", "grok-3-mini-beta"})


class XAIEngine(ResponsesAPIEngine):
	"""Engine implementation for xAI API integration.

	Uses the Responses API (client.responses.create) for web search support.
	Extends ResponsesAPIEngine with xAI-specific model config and reasoning.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.TEXT,
		ProviderCapability.WEB_SEARCH,
	}

	supported_attachment_formats: set[str] = {
		"image/gif",
		"image/jpeg",
		"image/png",
		"image/webp",
	}

	@cached_property
	def client(self) -> OpenAI:
		"""Create and configure the OpenAI client for xAI API."""
		super().client
		return OpenAI(
			api_key=self.account.api_key.get_secret_value(),
			base_url=self.account.custom_base_url
			or str(self.account.provider.base_url),
		)

	MODELS_JSON_URL = (
		"https://raw.githubusercontent.com/SigmaNight/model-metadata/"
		"master/data/x-ai.json"
	)

	def _postprocess_models(
		self, models: list[ProviderAIModel]
	) -> list[ProviderAIModel]:
		for m in models:
			if m.id in _XAI_REASONING_ONLY_IDS:
				m.reasoning = True
				m.reasoning_capable = False
			elif m.id in _XAI_REASONING_EFFORT_IDS:
				m.reasoning_capable = True
		return models

	def get_web_search_tool_definitions(
		self, model: ProviderAIModel
	) -> list[dict[str, str]]:
		"""Return web_search tool for xAI Responses API."""
		return [{"type": "web_search"}]

	def _build_completion_params(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Any,
		stop_block_index: int | None,
		model: ProviderAIModel,
		kwargs: dict[str, Any],
	) -> dict[str, Any]:
		params = super()._build_completion_params(
			new_block,
			conversation,
			system_message,
			stop_block_index,
			model,
			kwargs,
		)
		if model.id in _XAI_REASONING_EFFORT_IDS and new_block.reasoning_mode:
			effort = new_block.reasoning_effort or "high"
			if effort == "medium":
				effort = "high"
			params["reasoning"] = {"effort": effort}
		return params
