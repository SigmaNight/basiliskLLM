"""Module for xAI API integration.

This module provides the XAIEngine class for interacting with the xAI API,
implementing capabilities for both text and image generation.
"""

import logging
from functools import cached_property

from .base_engine import ProviderAIModel
from .openai_engine import OpenAIEngine, ProviderCapability

log = logging.getLogger(__name__)


class XAIEngine(OpenAIEngine):
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
			List of supported xAI models with their configurations.
		"""
		log.debug("Getting xAI models")
		# See <https://console.x.ai/team/default/models>
		models = [
			ProviderAIModel(
				id="grok-2-1212",
				# Translators: This is a model description
				description="",
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-2-vision-1212",
				# Translators: This is a model description
				description="",
				context_window=32768,
				max_temperature=2.0,
				default_temperature=1.0,
				vision=True,
			),
			ProviderAIModel(
				id="grok-3",
				# Translators: This is a model description
				description="",
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-3-mini",
				# Translators: This is a model description
				description="",
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-3-fast",
				# Translators: This is a model description
				description="",
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-3-mini-fast",
				# Translators: This is a model description
				description="",
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
		]
		return models
