"""Module for MistralAI API integration.

This module provides the MistralAIEngine class for interacting with the MistralAI API,
implementing capabilities for text generation using various MistralAI models.
"""

import logging
from functools import cached_property

from .base_engine import ProviderAIModel
from .openai_engine import OpenAIEngine, ProviderCapability

log = logging.getLogger(__name__)


class MistralAIEngine(OpenAIEngine):
	"""Engine implementation for MistralAI API integration.

	Extends OpenAIEngine to provide MistralAI-specific model configurations and capabilities.
	Supports text generation through various MistralAI models.

	Attributes:
		capabilities: Set of supported capabilities (currently text only).
	"""

	capabilities: set[ProviderCapability] = {ProviderCapability.TEXT}

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Retrieves available MistralAI models.

		Returns:
			List of supported MistralAI models with their configurations.
		"""
		log.debug("Getting MistralAI models")
		# See <https://docs.mistral.ai/getting-started/models/>
		models = [
			ProviderAIModel(
				id="ministral-3b-latest",
				name="Ministral 3B",
				# Translators: This is a model description
				description=_("World’s best edge model"),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="ministral-8b-latest",
				name="Ministral 8B",
				# Translators: This is a model description
				description=_(
					"Powerful edge model with extremely high performance/price ratio"
				),
				context_window=128000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="mistral-large-latest",
				name="Mistral Large",
				# Translators: This is a model description
				description=_(
					"Our top-tier reasoning model for high-complexity tasks with the latest version v2 released July 2024"
				),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="pixtral-large-latest",
				name="Pixtral Large",
				# Translators: This is a model description
				description=_(
					"Our frontier-class multimodal model released November 2024"
				),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
				vision=True,
			),
			ProviderAIModel(
				id="mistral-small-latest",
				name="Mistral Small",
				# Translators: This is a model description
				description=_(
					"Our latest enterprise-grade small model with the lastest version v2 released September 2024"
				),
				context_window=32000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="codestral-latest",
				name="Codestral",
				# Translators: This is a model description
				description=_(
					"Our cutting-edge language model for coding released May 2024"
				),
				context_window=256000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="pixtral-12b-2409",
				name="Pixtral",
				# Translators: This is a model description
				description=_(
					"A 12B model with image understanding capabilities in addition to text"
				),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
				vision=True,
			),
			ProviderAIModel(
				id="open-mistral-nemo",
				name="Mistral Nemo",
				# Translators: This is a model description
				description=_(
					"A 12B model built with the partnership with Nvidia. It is easy to use and a drop-in replacement in any system using Mistral 7B that it supersedes"
				),
				context_window=128000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="open-codestral-mamba",
				name="Codestral Mamba",
				# Translators: This is a model description
				description=_(
					"A Mamba 2 language model specialized in code generation"
				),
				context_window=256000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
		]
		return models
