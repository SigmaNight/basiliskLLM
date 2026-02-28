"""Module for xAI API integration.

This module provides the XAIEngine class for interacting with the xAI API,
implementing capabilities for both text and image generation.
"""

import logging
from functools import cached_property

from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

from .legacy_openai_engine import LegacyOpenAIEngine

log = logging.getLogger(__name__)


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

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Retrieves available xAI models.

		Returns:
			List of supported xAI models with their configurations, sorted from most recent to least recent.
		"""
		log.debug("Getting xAI models")
		# See <https://docs.x.ai/docs/models>
		models = [
			ProviderAIModel(
				id="grok-4-0709",
				# Translators: This is a model description
				description=_(
					"Flagship frontier model for complex tasks with 256K context, tool use and structured output."
				),
				context_window=256000,
				max_temperature=2.0,
				default_temperature=1.0,
				vision=True,
			),
			ProviderAIModel(
				id="grok-4-fast-reasoning",
				# Translators: This is a model description
				description=_(
					"High-throughput reasoning with 2M token context for rapid completions."
				),
				context_window=2000000,
				max_temperature=2.0,
				default_temperature=1.0,
				vision=True,
				reasoning=True,
			),
			ProviderAIModel(
				id="grok-4-fast-non-reasoning",
				# Translators: This is a model description
				description=_(
					"Fast completions without reasoning tokens, cost-efficient with 2M context."
				),
				context_window=2000000,
				max_temperature=2.0,
				default_temperature=1.0,
				vision=True,
			),
			ProviderAIModel(
				id="grok-code-fast-1",
				# Translators: This is a model description
				description=_(
					"Optimized for agentic coding tasks with 256K context."
				),
				context_window=256000,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-3",
				# Translators: This is a model description
				description=_(
					"Flagship model for enterprise tasks, extraction and coding."
				),
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-3-mini",
				# Translators: This is a model description
				description=_(
					"Cost-efficient, faster than Grok 3 for well-defined tasks."
				),
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-2-vision-1212",
				# Translators: This is a model description
				description=_(
					"Multimodal image understanding with 32K context."
				),
				context_window=32768,
				max_temperature=2.0,
				default_temperature=1.0,
				vision=True,
			),
		]
		return models
