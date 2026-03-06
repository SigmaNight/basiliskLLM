"""Module for xAI API integration.

This module provides the XAIEngine class for interacting with the xAI API,
implementing capabilities for both text and image generation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Generator

from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

from .legacy_openai_engine import LegacyOpenAIEngine

if TYPE_CHECKING:
	from openai.types.chat import ChatCompletion, ChatCompletionChunk

	from basilisk.conversation import Conversation, MessageBlock, SystemMessage

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


class XAIEngine(LegacyOpenAIEngine):
	"""Engine implementation for xAI API integration.

	Extends LegacyOpenAIEngine to provide xAI-specific model configurations and capabilities.
	Supports both text and image generation through the xAI API.

	Attributes:
		capabilities: Set of supported capabilities including text and image generation.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.TEXT,
	}

	MODELS_JSON_URL = "https://raw.githubusercontent.com/SigmaNight/model-metadata/master/data/x-ai.json"

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

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: SystemMessage | None,
		stop_block_index: int | None = None,
		**kwargs,
	) -> ChatCompletion | Generator[ChatCompletionChunk, None, None]:
		"""Add reasoning_effort for grok-3-mini when reasoning_mode is on."""
		model = self.get_model(new_block.model.model_id)
		if (
			model
			and model.id in _XAI_REASONING_EFFORT_IDS
			and new_block.reasoning_mode
		):
			effort = new_block.reasoning_effort or "high"
			if effort == "medium":
				effort = "high"
			kwargs["reasoning_effort"] = effort
		return super().completion(
			new_block, conversation, system_message, stop_block_index, **kwargs
		)
