"""Module for xAI API integration.

This module provides the XAIEngine class for interacting with the xAI API,
implementing capabilities for both text and image generation.
"""

import logging
from functools import cached_property

from .base_engine import ProviderAIModel
from .legacy_openai_engine import LegacyOpenAIEngine, ProviderCapability

log = logging.getLogger(__name__)


class XAIEngine(LegacyOpenAIEngine):
	"""Engine implementation for xAI API integration.

	Extends OpenAIEngine to provide xAI-specific model configurations and capabilities.
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
		# See <https://x.ai>
		models = [
			ProviderAIModel(
				id="grok-4",
				description="The most intelligent model from xAI, featuring native tool use, real-time search integration, and a context window of 256,000 tokens.",
				context_window=256000,
				max_temperature=2.0,
				default_temperature=1.0,
				vision=True,
			),
			ProviderAIModel(
				id="grok-4-heavy",
				description="The most powerful version of Grok 4, utilizing parallel test-time compute for multiple hypotheses, setting new standards in performance and reliability.",
				context_window=256000,
				max_temperature=2.0,
				default_temperature=1.0,
				vision=True,
			),
			ProviderAIModel(
				id="grok-3",
				description="A flagship model from xAI, offering advanced reasoning and a context window of 131,072 tokens.",
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-3-mini",
				description="A compact version of Grok 3, optimized for efficiency with a context window of 131,072 tokens.",
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-3-fast",
				description="A high-speed variant of Grok 3, designed for rapid text generation with a context window of 131,072 tokens.",
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-3-mini-fast",
				description="A fast and compact version of Grok 3, balancing speed and efficiency with a context window of 131,072 tokens.",
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-2-1212",
				description="Grok 2 model (Dec 2024), offering robust text generation capabilities with a context window of 131,072 tokens.",
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-2-vision-1212",
				description="Grok 2 vision model (Dec 2024), supporting image and text processing with a context window of 32,768 tokens.",
				context_window=32768,
				max_temperature=2.0,
				default_temperature=1.0,
				vision=True,
			),
			ProviderAIModel(
				id="grok",
				description="The original Grok model, providing foundational AI capabilities with a context window of 8,192 tokens.",
				context_window=8192,
				max_temperature=2.0,
				default_temperature=1.0,
			),
		]
		return models
